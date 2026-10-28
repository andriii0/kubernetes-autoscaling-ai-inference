"""Warm fixed replicas and verify Service distribution using native Ollama logs."""

import json
from collections import Counter
import re
import subprocess
from urllib.parse import quote

from records import timestamp


def warmup_pods(observer, pods, workload, timeout, warmup):
    records = []
    for pod in sorted(pods, key=lambda p: p["metadata"]["uid"]):
        name = pod["metadata"]["name"]
        route = (f"/api/v1/namespaces/{quote(observer.namespace, safe='')}/pods/"
                 f"{quote(name, safe='')}:11434/proxy/api/generate")

        def send(request, request_timeout):
            completed = subprocess.run(
                ["kubectl", "--context", observer.context, f"--request-timeout={request_timeout}s",
                 "create", "--raw", route, "-f", "-"],
                input=request.data.decode("utf-8"), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=request_timeout + 2, check=False)
            if completed.returncode:
                raise OSError(completed.stderr.strip() or f"pod proxy exited {completed.returncode}")
            return 200, json.loads(completed.stdout)

        record = warmup("http://pod-proxy", workload, timeout, sender=send)
        record.update(pod_uid=pod["metadata"]["uid"], pod_name=name, transport="kubernetes-pod-proxy",
                      ready_transition_at_utc=next(c.get("lastTransitionTime") for c in pod["status"]["conditions"]
                                                   if c["type"] == "Ready" and c["status"] == "True"))
        records.append(record)
        if not record["successful"]:
            break
    return {"phase": "warmup", "successful": len(records) == len(pods) and all(r["successful"] for r in records),
            "http_status": 200 if records and all(r["successful"] for r in records) else None,
            "started_at_utc": records[0]["started_at_utc"], "finished_at_utc": records[-1]["finished_at_utc"],
            "replicas": records}


def check_warmup(warm, identities, load_started):
    records = warm["replicas"]
    expected = {i["pod_uid"] for i in identities}
    if len(records) != len(expected) or {r["pod_uid"] for r in records} != expected:
        raise ValueError("warmup does not cover every selected replica exactly once")
    for record in records:
        if record["successful"] is not True or record["http_status"] != 200:
            raise ValueError("a replica warmup failed")
        if timestamp(record["finished_at_utc"]) > timestamp(load_started):
            raise ValueError("replica warmup overlaps measured load")


def capture_route(observer, service):
    return {"service": json.loads(observer.read("-n", observer.namespace, "get", "service", service, "-o", "json")),
            "endpoint_slices": json.loads(observer.read("-n", observer.namespace, "get", "endpointslices",
                                                       "-l", f"kubernetes.io/service-name={service}", "-o", "json"))}


def check_route(route, identities, deployment):
    service = route["service"]["spec"]
    if service.get("selector") != deployment["spec"]["selector"]["matchLabels"]:
        raise ValueError("Service selector does not match the selected Deployment")
    if not any(p.get("port") == 11434 and p.get("targetPort") == 11434 for p in service["ports"]):
        raise ValueError("Service does not target the Ollama API port")
    actual = []
    for item in route["endpoint_slices"]["items"]:
        for endpoint in item["endpoints"]:
            if endpoint.get("conditions", {}).get("ready") is not True:
                raise ValueError("Service has a non-ready endpoint")
            reference = endpoint["targetRef"]
            if reference.get("kind") != "Pod":
                raise ValueError("Service endpoint does not refer to a pod")
            actual.append(reference["uid"])
    expected = {i["pod_uid"] for i in identities}
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("Service endpoints do not match the selected replicas")


def capture_logs(observer, pods, container, folder, since):
    logs = folder / "pod-logs"
    logs.mkdir()
    for pod in pods:
        raw = observer.read("-n", observer.namespace, "logs", pod["metadata"]["name"], "-c", container,
                            "--timestamps=true", "--since-time", since)
        (logs / (pod["metadata"]["uid"] + ".log")).write_text(raw, encoding="utf-8")


def distribution(folder, metadata, counts, completed_events):
    """Count server completions during the load process, excluding preceding pod warmups."""
    result = {}
    server_statuses = Counter()
    beginning = timestamp(metadata["load_process_started_at_utc"])
    ending = timestamp(metadata["load_process_finished_at_utc"])
    for identity in metadata["initial_identity"]:
        statuses = []
        for line in (folder / "pod-logs" / (identity["pod_uid"] + ".log")).read_text(encoding="utf-8").splitlines():
            if not re.search(r'\bPOST\s+"/api/generate"', line):
                continue
            at, message = line.split(" ", 1)
            match = re.search(r'\[GIN\].*?\|\s*(\d{3})\s*\|', message)
            if match is None:
                raise ValueError("unrecognized Ollama generation access log")
            if beginning <= timestamp(at) <= ending:
                statuses.append(int(match[1]))
        server_statuses.update(statuses)
        result[identity["pod_uid"]] = {"completed": len(statuses), "http_200": statuses.count(200)}
    if metadata.get("protocol_version"):
        return {"pods": result, "all_pods_active": all(r["completed"] > 0 for r in result.values()),
                "started_at_utc": metadata["load_process_started_at_utc"],
                "finished_at_utc": metadata["load_process_finished_at_utc"],
                "method": "Observed server completions; client outcomes and server drain are separate"}
    if not all(r["completed"] for r in result.values()):
        raise ValueError("not every replica handled a measured Service request")
    if sum(r["completed"] for r in result.values()) != counts["completed"]:
        raise ValueError("pod access log counts do not match completed client requests")
    # HTTP 200 can still contain an empty or invalid model response. Compare transport status,
    # while the shared request validator keeps semantic failures in the client outcome counts.
    if server_statuses != Counter(event["http_status"] for event in completed_events):
        raise ValueError("pod HTTP status counts do not match client HTTP statuses")
    return {"pods": result, "started_at_utc": metadata["load_process_started_at_utc"],
            "finished_at_utc": metadata["load_process_finished_at_utc"],
            "method": "Ollama completion logs; aggregate pod counts, not client-request attribution"}

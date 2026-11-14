"""Read saved records and interpret timestamps, statistics and replica identities."""

import json
import math
from datetime import datetime, timezone


def percentile(values, fraction):
    """Linear interpolation at (n - 1) * fraction, matching the k6 trend summary."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.timestamp()


def iso_time(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def pilot_identity(sample, deployment="ollama", container="ollama", replicas=1, allow_resource_gaps=False):
    """Require stable fixed replicas and complete counters; retain the historical one-pod shape."""
    if replicas not in (1, 3):
        raise ValueError("only one or three fixed replicas are supported")
    if any(not allow_resource_gaps or e.get("category") != "missing_resource" for e in sample["errors"]):
        raise ValueError("cluster collection contains errors")
    pods = sample["pods"]["items"]
    if len(pods) != replicas:
        raise ValueError("pilot requires exactly one selected pod" if replicas == 1 else
                         "fixed check requires exactly three selected pods")
    target = next((d for d in sample["deployments"]["items"] if d["metadata"]["name"] == deployment), None)
    if target is None:
        raise ValueError("pilot Deployment is missing")
    if (target["spec"].get("replicas", 1) != replicas or any(target["status"].get(key) != replicas for key in
            ("replicas", "readyReplicas", "updatedReplicas", "availableReplicas"))
            or target["status"].get("observedGeneration", 0) < target["metadata"].get("generation", 1)):
        raise ValueError("Deployment is not stable at one replica" if replicas == 1 else
                         "Deployment is not stable at three replicas")
    if any(h["spec"]["scaleTargetRef"].get("kind") == "Deployment"
           and h["spec"]["scaleTargetRef"].get("name") == deployment for h in sample["hpa"]["items"]):
        raise ValueError("an HPA targets the pilot Deployment")
    identities = []
    for pod in pods:
        if pod.get("metadata", {}).get("deletionTimestamp") or pod["status"].get("phase") != "Running":
            raise ValueError("pilot pod is not running")
        if not any(c["type"] == "Ready" and c["status"] == "True" for c in pod["status"].get("conditions", [])):
            raise ValueError("pilot pod is not Ready")
        status = next((c for c in pod["status"]["containerStatuses"] if c["name"] == container), None)
        if status is None:
            raise ValueError("pilot container is missing from pod status")
        if not status.get("ready") or "running" not in status.get("state", {}):
            raise ValueError("pilot container is not ready/running")
        labels = pod["metadata"].get("labels", {})
        selector = target["spec"]["selector"]
        if selector.get("matchExpressions") or not selector.get("matchLabels") or any(
                labels.get(k) != v for k, v in selector["matchLabels"].items()):
            raise ValueError("selected pod does not match the pilot Deployment")
        for scope in (() if allow_resource_gaps else ("container", "node")):
            matching = [r for r in sample["resource_usage"] if r["scope"] == scope and r["node"] == pod["spec"]["nodeName"]
                        and (scope == "node" or (r["pod_uid"] == pod["metadata"]["uid"] and r["container"] == container))]
            if len(matching) != 1 or any(matching[0].get(key) is None for key in
                                        ("cpu_usage_seconds_total", "memory_working_set_bytes")):
                raise ValueError(f"missing {scope} resource counters")
        identities.append({"pod_uid": pod["metadata"]["uid"], "container_id": status["containerID"],
                           "restart_count": status["restartCount"], "image_id": status["imageID"]})
    if len({i["pod_uid"] for i in identities}) != replicas:
        raise ValueError("duplicate selected pod identity")
    return identities[0] if replicas == 1 else sorted(identities, key=lambda i: i["pod_uid"])


def read_jsonl(path):
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                raise ValueError(f"{path.name}:{line_number}: empty record")
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{path.name}:{line_number}: record must be a JSON object")
            yield record

"""Read and reconcile pilot collection evidence; never modify input files."""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.timestamp()


def iso_time(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def pilot_identity(sample, deployment="ollama", container="ollama", replicas=1):
    """Require stable fixed replicas and complete counters; retain the historical one-pod shape."""
    if replicas not in (1, 3):
        raise ValueError("only one or three fixed replicas are supported")
    if sample["errors"]:
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
        for scope in ("container", "node"):
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


def reconcile(folder, metadata):
    """Count client outcomes independently of k6 totals; retain invalid/partial evidence."""
    report = {"schema_version": 1, "valid": False, "errors": [],
              "warnings": list(metadata.get("warnings", [])), "counts": {}, "load_window": None}
    errors = report["errors"]
    try:
        if metadata["errors"]:
            errors.append("launcher reported errors")
        if metadata["k6_exit_code"] not in (0, 99) or metadata["collector_exit_code"] != 0:
            errors.append("load/collection processes did not finish normally")
        warm = json.loads((folder / "warmup.json").read_text(encoding="utf-8"))
        if warm["phase"] != "warmup" or warm["successful"] is not True or warm["http_status"] != 200:
            errors.append("warmup was not successful")
        if metadata.get("expected_replicas", 1) == 3:
            from fixed_replicas import check_route, check_warmup
            check_warmup(warm, metadata["initial_identity"], metadata["load_process_started_at_utc"])
            check_route(json.loads((folder / "service-route.json").read_text(encoding="utf-8")),
                        metadata["initial_identity"], metadata["deployment_snapshot"])
        if timestamp(warm["finished_at_utc"]) > timestamp(metadata["load_process_started_at_utc"]):
            errors.append("warmup overlaps measured load")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(f"run evidence: {error}")
    # Archive diagnostics do not decide whether the request/resource measurements are complete.
    try:
        required = {"inference.js", "workload.json", "run_pilot.py", "observe.py", "pilot_records.py"}
        if metadata.get("expected_replicas", 1) == 3 or metadata.get("mode") == "autoscaling":
            required.add("fixed_replicas.py")
        if metadata.get("mode") == "autoscaling":
            required.add("autoscaling.py")
        if set(metadata["source_sha256"]) != required:
            report["warnings"].append("incomplete executable input hashes")
        for name in required:
            if hashlib.sha256((folder / "inputs" / name).read_bytes()).hexdigest() != metadata["source_sha256"][name]:
                report["warnings"].append(f"executable input changed: {name}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        report["warnings"].append(f"input archive: {error}")
    starts, completions = {}, {}
    try:
        for event in read_jsonl(folder / "request-events.jsonl"):
            if event["schema_version"] != 1 or event["run_id"] != metadata["run_id"] or event["phase"] != "load":
                raise ValueError("request event has an unexpected schema, run or phase")
            kind = event["event"]
            if kind not in ("started", "completed"):
                raise ValueError("unknown request event")
            target = starts if kind == "started" else completions
            key = event["request_id"]
            if key in target:
                raise ValueError(f"duplicate {kind} event: {key}")
            timestamp(event["started_at_utc"])
            target[key] = event
            if kind == "completed":
                if key not in starts:
                    raise ValueError("completion without preceding start")
                for field in ("started_at_utc", "scenario_started_at_utc", "scenario", "iteration", "vu"):
                    if event[field] != starts[key][field]:
                        raise ValueError(f"request identity changed: {field}")
                elapsed = (timestamp(event["finished_at_utc"]) - timestamp(event["started_at_utc"])) * 1000
                if elapsed < 0 or not math.isfinite(event["duration_ms"]) or abs(elapsed - event["duration_ms"]) > 1:
                    raise ValueError("inconsistent request duration")
                if event["outcome"] not in ("success", "failure"):
                    raise ValueError("unknown request outcome")
                if (event["outcome"] == "success") != (event["error_category"] is None):
                    raise ValueError("inconsistent request outcome/category")
                if event["outcome"] == "success" and event["http_status"] != 200:
                    raise ValueError("successful request has non-200 status")
                for field in ("output_tokens", "model_load_ms"):
                    value = event[field]
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                              or not math.isfinite(value) or value < 0):
                        raise ValueError(f"invalid optional measurement: {field}")
                if event["output_tokens"] is not None and (type(event["output_tokens"]) is not int
                                                           or event["output_tokens"] > 2**53 - 1):
                    raise ValueError("output_tokens must be a nonnegative safe integer")
        unfinished = len(starts.keys() - completions.keys())
        successful = sum(e["outcome"] == "success" for e in completions.values())
        report["counts"] = {"started": len(starts), "completed": len(completions),
                            "successful": successful, "failed": len(completions) - successful,
                            "unfinished": unfinished, "dropped": None}
        if not starts:
            errors.append("no requests started")
        if unfinished:
            errors.append(f"{unfinished} requests have no completion (server-side drain is unproven)")
        raw = {}
        for record in read_jsonl(folder / "requests.json"):
            if record.get("type") == "Point":
                name = record["metric"]
                value = record["data"]["value"]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"invalid raw metric value: {name}")
                raw[name] = raw.get(name, 0) + value
        summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))["metrics"]
        expected = {"requests_started": len(starts), "requests_completed": len(completions),
                    "http_reqs": len(completions), "iterations": len(completions)}
        for metric, count in expected.items():
            entry = summary[metric]
            if raw.get(metric, 0) != count or entry.get("values", entry)["count"] != count:
                errors.append(f"{metric} does not reconcile with request events")
        failures = summary["inference_errors"]
        failures = failures.get("values", failures)
        if raw.get("inference_errors", 0) != report["counts"]["failed"] or failures["passes"] != report["counts"]["failed"] or failures["fails"] != successful:
            errors.append("inference_errors does not reconcile with request outcomes")
        dropped = summary["dropped_iterations"]
        report["counts"]["dropped"] = dropped.get("values", dropped)["count"]
        if raw.get("dropped_iterations", 0) != report["counts"]["dropped"]:
            errors.append("dropped_iterations does not reconcile")
        if starts:
            scenario_starts = {timestamp(e["scenario_started_at_utc"]) for e in starts.values()}
            if len(scenario_starts) != 1:
                raise ValueError("expected a single load scenario")
            beginning = scenario_starts.pop()
            scheduled_end = beginning + metadata["duration_seconds"]
            finished = max([scheduled_end] + [timestamp(e["finished_at_utc"]) for e in completions.values()])
            for event in starts.values():
                # k6 scenario.startTime and Date.now() are integer millisecond clocks.
                # Permit one clock tick at either boundary, without changing the actual times.
                offset_ms = round((timestamp(event["started_at_utc"]) - beginning) * 1000)
                duration_ms = round(metadata["duration_seconds"] * 1000)
                if not -1 <= offset_ms <= duration_ms + 1:
                    errors.append("request start outside scheduled load interval")
                    break
                if offset_ms < 0 or offset_ms > duration_ms:
                    report["warnings"].append("request start within 1 ms timestamp boundary tolerance")
            report["load_window"] = {"started_at_utc": iso_time(beginning),
                                     "scheduled_end_at_utc": iso_time(scheduled_end),
                                     "client_drain_end_at_utc": iso_time(finished),
                                     "request_start_tolerance_ms": 1}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(f"request evidence: {error}")
    report["events_read"] = {"started": len(starts), "completed": len(completions)}

    try:
        times = []
        error_count = 0
        identity = metadata["initial_identity"]
        for sample in read_jsonl(folder / "cluster.jsonl"):
            observed = timestamp(sample["time"])
            if times and observed <= times[-1]:
                errors.append("observation times are not strictly increasing")
            if times and observed - times[-1] > 2 * metadata["observer_interval_seconds"]:
                errors.append("observation gap exceeds twice the configured interval")
            times.append(observed)
            error_count += len(sample["errors"])
            try:
                if metadata.get("mode") != "autoscaling" and pilot_identity(sample, metadata["deployment"], metadata["container"], metadata.get("expected_replicas", 1)) != identity:
                    errors.append("pilot container identity or restart count changed")
            except (ValueError, KeyError, StopIteration, TypeError, AttributeError) as error:
                errors.append(f"invalid cluster sample: {error}")
        report["observation"] = {"samples": len(times), "collection_errors": error_count,
                                 "max_gap_seconds": max((b - a for a, b in zip(times, times[1:])), default=None)}
        window = report["load_window"]
        if len(times) < 2 or (window and (times[0] > timestamp(window["started_at_utc"])
                                        or times[-1] < timestamp(window["client_drain_end_at_utc"]))):
            errors.append("cluster observations do not bracket the load and drain interval")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(f"cluster evidence: {error}")
    if metadata.get("expected_replicas", 1) == 3:
        try:
            from fixed_replicas import distribution
            report["distribution"] = distribution(folder, metadata, report["counts"], completions.values())
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            errors.append(f"Service distribution: {error}")
    if metadata.get("mode") == "autoscaling":
        try:
            from autoscaling import check_samples, log_summary
            if metadata['profile'] == 'burst' and sum(s['seconds'] for s in metadata['workload']['burst_stages']) != metadata['duration_seconds']:
                errors.append('burst duration does not match archived workload stages')
            samples = list(read_jsonl(folder / "cluster.jsonl"))
            dynamic_errors, gaps = check_samples(samples, metadata)
            errors.extend(dynamic_errors)
            report["resource_gaps"] = gaps
            report["logs"] = log_summary(folder, metadata, samples)
            errors.extend(report["logs"]["errors"])
            report["observation"]["resource_gap_samples"] = len({g["time"] for g in gaps})
        except (OSError, ValueError, KeyError, StopIteration, TypeError, AttributeError) as error:
            errors.append(f"autoscaling evidence: {error}")
    report["errors"] = list(dict.fromkeys(errors))
    report["valid"] = not report["errors"]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    metadata = json.loads((args.run_dir / "metadata.json").read_text(encoding="utf-8"))
    report = reconcile(args.run_dir, metadata)
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

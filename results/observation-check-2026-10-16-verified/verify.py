"""Independently inspect saved observer-check artifacts; no cluster access."""
import json
import math
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

root = Path(sys.argv[1])
def read_json(name):
    return json.loads((root / name).read_text(encoding="utf-8-sig"))

metadata = read_json("metadata.json")
assert all(metadata[key] == 0 for key in ("baseline_exit_code", "load_exit_code", "observer_exit_code"))
rows = [json.loads(line) for line in (root / "cluster.jsonl").read_text(encoding="utf-8").splitlines()]
assert len(rows) >= 25
assert not any(row["errors"] for row in rows)
timestamps = [datetime.fromisoformat(row["time"]) for row in rows]
intervals = [(b - a).total_seconds() for a, b in zip(timestamps, timestamps[1:])]
assert all(t.utcoffset().total_seconds() == 0 for t in timestamps)
assert (timestamps[-1] - timestamps[0]).total_seconds() >= 140
assert all(row["hpa"]["items"] == [] for row in rows)
assert all(row["deployments"]["items"][0]["status"]["readyReplicas"] == 1 for row in rows)

containers = []
previous = None
for row in rows:
    records = [r for r in row["resource_usage"] if r["scope"] == "container"]
    assert len(records) == 1
    record = records[0]
    assert record["namespace"] == "inference" and record["container"] == "ollama"
    raw = row["kubelet"][record["node"]]["raw"]
    # Verify the raw metric's labels and units independently of the parser.
    for name, field in (("container_cpu_usage_seconds_total", "cpu_usage_seconds_total"),
                        ("container_memory_working_set_bytes", "memory_working_set_bytes")):
        line = next(line for line in raw.splitlines() if line.startswith(name + "{")
                    and f'pod="{record["pod"]}"' in line)
        match = re.search(r"\}\s+(\S+)\s+(\d+)$", line)
        assert match and float(match[1]) == record[field]
    assert record["memory_working_set_bytes"] > 0
    if record["cpu_cores"] is not None:
        assert previous is not None
        delta = record["cpu_usage_seconds_total"] - previous["cpu_usage_seconds_total"]
        seconds = (record["cpu_timestamp_ms"] - previous["cpu_timestamp_ms"]) / 1000
        assert seconds > 0 and delta >= 0
        assert math.isclose(record["cpu_cores"], delta / seconds, rel_tol=1e-5)
    containers.append((datetime.fromisoformat(row["time"]), record))
    previous = record
assert len({r["pod_uid"] for _, r in containers}) == 1
assert len({r["restart_count"] for _, r in containers}) == 1
assert len({r["cpu_timestamp_ms"] for _, r in containers}) > 5

checks = {}
for prefix in ("baseline-", ""):
    summary = read_json(prefix + "summary.json")["metrics"]
    points = [json.loads(line) for line in (root / (prefix + "requests.json")).read_text(encoding="utf-8").splitlines()]
    latencies = [p["data"]["value"] for p in points if p.get("type") == "Point" and p.get("metric") == "successful_latency_ms"]
    errors = [p["data"]["value"] for p in points if p.get("type") == "Point" and p.get("metric") == "inference_errors"]
    assert len(latencies) == len(errors) == summary["iterations"]["count"]
    assert sum(errors) == 0 and summary["dropped_iterations"]["count"] == 0
    ordered = sorted(latencies)
    index = .95 * (len(ordered) - 1)
    lower = math.floor(index)
    p95 = ordered[lower] + (index - lower) * (ordered[math.ceil(index)] - ordered[lower])
    assert math.isclose(p95, summary["successful_latency_ms"]["p(95)"])
    assert math.isclose(statistics.mean(latencies), summary["successful_latency_ms"]["avg"])
    checks["baseline" if prefix else "observed"] = {
        "completed": len(latencies), "errors": sum(errors), "dropped": 0,
        "mean_ms": statistics.mean(latencies), "p95_ms": p95,
    }

load_start = datetime.fromisoformat(metadata["load_started_at_utc"])
load_end = datetime.fromisoformat(metadata["load_finished_at_utc"])
idle = [r["cpu_cores"] for t, r in containers if t < load_start and r["cpu_cores"] is not None]
load = [r["cpu_cores"] for t, r in containers if load_start <= t <= load_end and r["cpu_cores"] is not None]
assert idle and load and max(load) > statistics.mean(idle)
checks.update({
    "samples": len(rows), "collection_errors": 0,
    "observation_span_seconds": (timestamps[-1] - timestamps[0]).total_seconds(),
    "poll_interval_mean_seconds": statistics.mean(intervals),
    "poll_interval_max_seconds": max(intervals),
    "collection_duration_max_seconds": max(r["collection_duration_seconds"] for r in rows),
    "valid_container_cpu_rates": sum(r["cpu_cores"] is not None for _, r in containers),
    "unique_container_source_timestamps": len({r["cpu_timestamp_ms"] for _, r in containers}),
    "container_peak_memory_mib": max(r["memory_working_set_bytes"] for _, r in containers) / 1048576,
    "idle_mean_cpu_cores": statistics.mean(idle), "load_mean_cpu_cores": statistics.mean(load),
    "load_peak_cpu_cores": max(load),
})
print(json.dumps(checks, indent=2))
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
print("PASS: live observations, resource units, and request totals verified")

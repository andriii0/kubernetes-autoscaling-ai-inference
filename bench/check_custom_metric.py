"""Save a read-only check of an installed candidate stack; never start workload."""

import argparse
import json
import math
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode

from custom_metrics import GATEWAY, METRIC, NAMESPACE, infrastructure_identity, selector, validate_signal, validate_observer_interval, clock_point
from observe import Observer


def check(observer, record):
    """A single idle-path check, not admission to the comparative experiment."""
    def read(name, *args):
        raw = observer.read(*args)
        record[name] = json.loads(raw)
        return record[name]

    record["server_version"] = read("server_version", "get", "--raw", "/version")
    before = read("pods_before", "-n", NAMESPACE, "get", "pods", "-l", "experiment=custom-metric-hpa", "-o", "json")
    identity = infrastructure_identity(before)
    record["identity"] = identity
    registered = read("api_service", "get", "apiservice", "v1beta1.custom.metrics.k8s.io", "-o", "json")
    spec = registered.get("spec", {})
    if spec.get("service", {}).get("name") != "inference-metrics-adapter" or spec.get("service", {}).get("namespace") != NAMESPACE:
        raise ValueError("custom metrics API belongs to a different installation")
    if not any(c.get("type") == "Available" and c.get("status") == "True"
               for c in registered.get("status", {}).get("conditions", [])):
        raise ValueError("custom metrics API is not Available")
    prefix = f"/api/v1/namespaces/{NAMESPACE}/services/http:inference-prometheus:9090/proxy/api/v1/query?"
    start, start_monotonic, start_uncertainty = clock_point()
    clock = read("prometheus_clock", "get", "--raw", prefix + urlencode({"query": "time()"}))
    end, end_monotonic, end_uncertainty = clock_point()
    data = clock.get("data", {})
    if clock.get("status") != "success" or data.get("resultType") != "scalar":
        raise ValueError("cannot check the Prometheus clock")
    server_time = float(data["result"][1])
    if not math.isfinite(server_time):
        raise ValueError("Prometheus clock is not finite")
    record["clock_bounds"] = {"sent_at": start, "received_at": end, "server_time": server_time, "tolerance_seconds": 1}
    record["clock_bounds"].update(sent_monotonic=start_monotonic, received_monotonic=end_monotonic,
                                  sent_clock_uncertainty=start_uncertainty, received_clock_uncertainty=end_uncertainty)
    validate_observer_interval(start, end, start_monotonic, end_monotonic, start_uncertainty, end_uncertainty)
    if not start - 1 <= server_time <= end + 1:
        raise ValueError("Prometheus and observer clocks differ by more than one second")
    evaluated = time.time()
    raw = selector('namespace="inference",service="inference-gateway"')
    up = 'up{job="inference-gateway",namespace="inference",service="inference-gateway"}'
    replies = [read(name, "get", "--raw", prefix + urlencode({"query": query, "time": evaluated}))
               for name, query in (("source", raw), ("source_time", f"timestamp({raw})"),
                                   ("health", up), ("health_time", f"timestamp({up})"))]
    exposed = read("adapter", "get", "--raw",
                   f"/apis/custom.metrics.k8s.io/v1beta1/namespaces/{NAMESPACE}/services/{GATEWAY}/{METRIC}")
    received = time.time()
    record["signal"] = validate_signal(*replies, exposed, gateway_uid=identity[GATEWAY]["uid"], received_at=received)
    after = read("pods_after", "-n", NAMESPACE, "get", "pods", "-l", "experiment=custom-metric-hpa", "-o", "json")
    if infrastructure_identity(after) != identity:
        raise ValueError("metrics infrastructure changed during the check")
    record["status"] = "signal-check-passed"
    record["scope"] = "One idle observation; concurrency, faults, resource headroom and experiment admission remain unverified"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--context", default="ai-lab")
    args = parser.parse_args(argv)
    folder = args.output_dir.resolve()
    try:
        folder.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        parser.exit(1, f"Cannot create new check folder: {error}\n")
    record = {"status": "failed", "context": args.context, "errors": [], "measured_load_started": False}
    try:
        check(Observer(args.context, NAMESPACE, "app=ollama"), record)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError) as error:
        record["errors"].append(str(error))
    finally:
        (folder / "check.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(record["status"])
    for error in record["errors"]:
        print(error)
    return 0 if record["status"] == "signal-check-passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

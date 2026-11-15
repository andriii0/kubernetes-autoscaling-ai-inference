"""Save read-only Kubernetes state and kubelet resource samples as JSONL."""

import argparse
import json
import math
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


RESOURCE_METRICS = {
    "container_cpu_usage_seconds_total",
    "container_memory_working_set_bytes",
    "container_start_time_seconds",
    "node_cpu_usage_seconds_total",
    "node_memory_working_set_bytes",
    "resource_scrape_error",
}
LABEL = re.compile(r'([a-zA-Z_]\w*)="((?:\\.|[^"\\])*)"(?:,|$)')
SAMPLE = re.compile(r"^(\w+)(?:\{(.*?)\})?\s+(\S+)(?:\s+(-?\d+))?$")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def parse_resource_metrics(raw):
    """Parse only the kubelet resource series used by this experiment."""
    samples = []
    for line in raw.splitlines():
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[\s{]", line, maxsplit=1)[0]
        if name not in RESOURCE_METRICS:
            continue
        match = SAMPLE.fullmatch(line)
        if not match:
            raise ValueError(f"Malformed resource sample: {name}")
        labels = {}
        label_text = match[2] or ""
        position = 0
        while position < len(label_text):
            label = LABEL.match(label_text, position)
            if not label or label[1] in labels:
                raise ValueError(f"Malformed resource labels: {name}")
            labels[label[1]] = json.loads('"' + label[2] + '"')
            position = label.end()
        value = float(match[3])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid resource value: {name}")
        samples.append({
            "name": name,
            "labels": labels,
            "value": value,
            "timestamp_ms": int(match[4]) if match[4] else None,
        })
    if not samples:
        raise ValueError("No expected kubelet resource metrics found")
    return samples


def derive_resource_usage(samples, pods, node, observed_at, previous):
    """Keep instance identity and use counter deltas only for consecutive samples."""
    grouped = {}
    for sample in samples:
        if sample["name"] == "resource_scrape_error":
            continue
        labels = sample["labels"]
        if sample["name"].startswith("container_"):
            key = ("container", labels.get("namespace"), labels.get("pod"), labels.get("container"))
        else:
            key = ("node", None, None, None)
        grouped.setdefault(key, {})[sample["name"]] = sample

    records = []
    current = {}
    for (scope, namespace, pod_name, container), metrics in grouped.items():
        pod = pods.get((namespace, pod_name)) if scope == "container" else None
        if scope == "container" and pod is None:
            continue
        prefix = "container" if scope == "container" else "node"
        cpu = metrics.get(f"{prefix}_cpu_usage_seconds_total")
        memory = metrics.get(f"{prefix}_memory_working_set_bytes")
        started = metrics.get("container_start_time_seconds")
        status = next((item for item in (pod or {}).get("status", {}).get("containerStatuses", [])
                       if item["name"] == container), {})
        uid = (pod or {}).get("metadata", {}).get("uid")
        # UID and restart count prevent deltas across a replaced container.
        identity = (node, scope, uid, container, status.get("restartCount"),
                    started["value"] if started else None)
        cpu_time = None
        clock = None
        if cpu:
            clock = "source" if cpu["timestamp_ms"] is not None else "collection"
            cpu_time = cpu["timestamp_ms"] / 1000 if clock == "source" else observed_at
        cores = None
        old = previous.get(identity)
        if cpu and old and old["clock"] == clock:
            elapsed = cpu_time - old["time"]
            delta = cpu["value"] - old["counter"]
            if elapsed > 0 and delta >= 0:
                cores = delta / elapsed
        if cpu:
            current[identity] = {"clock": clock, "time": cpu_time, "counter": cpu["value"]}
        records.append({
            "node": node, "scope": scope, "namespace": namespace, "pod": pod_name,
            "pod_uid": uid, "container": container, "restart_count": status.get("restartCount"),
            "container_start_time_seconds": started["value"] if started else None,
            "cpu_usage_seconds_total": cpu["value"] if cpu else None,
            "cpu_timestamp_ms": cpu["timestamp_ms"] if cpu else None,
            "cpu_clock": clock, "cpu_cores": cores,
            "memory_working_set_bytes": memory["value"] if memory else None,
            "memory_timestamp_ms": memory["timestamp_ms"] if memory else None,
        })
    return records, current


class Observer:
    def __init__(self, context="ai-lab", namespace="inference", selector="app=ollama", timeout=5):
        self.context = context
        self.namespace = namespace
        self.selector = selector
        self.timeout = timeout
        self.previous = {}

    def read(self, *args):
        result = subprocess.run(
            ["kubectl", "--context", self.context, f"--request-timeout={self.timeout}s", *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=self.timeout + 2, check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or f"kubectl exit code {result.returncode}")
        return result.stdout

    def collect(self, interval):
        started = time.monotonic()
        sample = {
            "schema_version": 1, "time": utc_now(), "context": self.context,
            "namespace": self.namespace, "selector": self.selector,
            "sources": {}, "errors": [], "kubelet": {}, "resource_usage": [],
        }

        def fetch(source, args, parser=json.loads):
            timing = {"started_at": utc_now()}
            try:
                raw = self.read(*args)
                value = parser(raw)
            except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as error:
                message = str(error)[:2000]
                sample["errors"].append({"source": source, "message": message})
                print(f"{source}: {message}", file=sys.stderr, flush=True)
                value = None
            timing["finished_at"] = utc_now()
            sample["sources"][source] = timing
            return value

        sample["pods"] = fetch("pods", ["-n", self.namespace, "get", "pods",
                                         "-l", self.selector, "-o", "json"])
        # A Deployment's own labels need not match its pod-template labels.
        sample["deployments"] = fetch("deployments", ["-n", self.namespace,
                                                       "get", "deployments", "-o", "json"])
        sample["hpa"] = fetch("hpa", ["-n", self.namespace, "get", "hpa", "-o", "json"])
        sample["nodes"] = fetch("nodes", ["get", "nodes", "-o", "json"])
        sample["resources"] = fetch("metrics_server", ["get", "--raw",
            f"/apis/metrics.k8s.io/v1beta1/namespaces/{quote(self.namespace, safe='')}/pods"])

        pods = {(p["metadata"]["namespace"], p["metadata"]["name"]): p
                for p in (sample["pods"] or {}).get("items", [])}
        node_names = {p.get("spec", {}).get("nodeName") for p in pods.values()}
        node_names.discard(None)
        current = {}
        for node in sorted(node_names):
            source = f"kubelet/{node}"
            raw = fetch(source, ["get", "--raw",
                f"/api/v1/nodes/{quote(node, safe='')}/proxy/metrics/resource"], lambda text: text)
            resources = {"raw": raw, "metrics": None} if raw is not None else None
            sample["kubelet"][node] = resources
            if raw is not None:
                try:
                    resources["metrics"] = parse_resource_metrics(raw)
                    if any(m["name"] == "resource_scrape_error" and m["value"] != 0
                           for m in resources["metrics"]):
                        raise ValueError("kubelet reports resource_scrape_error")
                except ValueError as error:
                    sample["errors"].append({"source": source, "message": str(error)})
                    print(f"{source}: {error}", file=sys.stderr, flush=True)
                    continue
                records, counters = derive_resource_usage(
                    resources["metrics"], pods, node, time.monotonic(), self.previous)
                sample["resource_usage"].extend(records)
                current.update(counters)
                expected = {(p["metadata"]["name"], c["name"])
                            for p in pods.values() if p.get("spec", {}).get("nodeName") == node
                            for c in p.get("status", {}).get("containerStatuses", [])
                            if "running" in c.get("state", {})}
                found = {(r["pod"], r["container"]) for r in records
                         if r["scope"] == "container" and r["cpu_usage_seconds_total"] is not None
                         and r["memory_working_set_bytes"] is not None}
                if expected - found:
                    sample["errors"].append({"source": source,
                        "category": "missing_resource", "message": f"Missing CPU/memory for running containers: {sorted(expected - found)}"})
                node_records = [r for r in records if r["scope"] == "node"]
                if not node_records or any(r["cpu_usage_seconds_total"] is None or
                                          r["memory_working_set_bytes"] is None for r in node_records):
                    sample["errors"].append({"source": source, "category": "missing_resource", "message": "Missing node CPU/memory"})
        # A failed sample clears its counters: do not bridge observation gaps.
        self.previous = current
        sample["collection_finished_at"] = utc_now()
        sample["collection_duration_seconds"] = time.monotonic() - started
        sample["overrun_seconds"] = max(0, sample["collection_duration_seconds"] - interval)
        return sample


def positive_number(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return number


from run_lock import exclusive_main


@exclusive_main
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new JSONL file; existing files are never overwritten")
    parser.add_argument("--context", default="ai-lab")
    parser.add_argument("--namespace", default="inference")
    parser.add_argument("--selector", default="app=ollama")
    parser.add_argument("--interval", type=positive_number, default=5, help="target poll interval in seconds")
    parser.add_argument("--timeout", type=positive_number, default=5, help="timeout per kubectl call in seconds")
    parser.add_argument("--duration", type=positive_number, help="stop after this many seconds; otherwise Ctrl+C")
    args = parser.parse_args(argv)
    observer = Observer(args.context, args.namespace, args.selector, args.timeout)
    count = 0
    error_count = 0
    started = time.monotonic()
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            try:
                while True:
                    cycle = time.monotonic()
                    sample = observer.collect(args.interval)
                    output.write(json.dumps(sample, ensure_ascii=False, allow_nan=False) + "\n")
                    output.flush()
                    count += 1
                    error_count += len(sample["errors"])
                    remaining = args.duration - (time.monotonic() - started) if args.duration else math.inf
                    if remaining <= 0:
                        break
                    pause = max(0, args.interval - (time.monotonic() - cycle))
                    time.sleep(min(pause, remaining))
                    if args.duration and time.monotonic() - started >= args.duration:
                        break
            except KeyboardInterrupt:
                pass
    except OSError as error:
        print(f"Cannot create observation file: {error}", file=sys.stderr)
        return 2
    print(f"Saved {count} samples, {error_count} collection errors: {args.output}", flush=True)
    return 1 if error_count or count == 0 else 0


if __name__ == "__main__":
    sys.exit(main())

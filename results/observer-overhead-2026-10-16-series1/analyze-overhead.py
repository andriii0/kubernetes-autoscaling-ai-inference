"""Verify and summarize a completed, counterbalanced observer overhead series."""
import csv
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def percentile(values, fraction):
    values = sorted(values)
    position = fraction * (len(values) - 1)
    lower = math.floor(position)
    return values[lower] + (position - lower) * (values[math.ceil(position)] - values[lower])


def snapshot_identity(path):
    items = read_json(path)["items"]
    deployment = next(i for i in items if i["kind"] == "Deployment" and i["metadata"]["name"] == "ollama")
    pods = [i for i in items if i["kind"] == "Pod" and i["metadata"].get("labels", {}).get("app") == "ollama"]
    assert len(pods) == 1 and pods[0]["status"]["phase"] == "Running"
    assert deployment["spec"]["replicas"] == deployment["status"]["readyReplicas"] == 1
    assert not any(i["kind"] == "HorizontalPodAutoscaler" for i in items)
    containers = pods[0]["status"]["containerStatuses"]
    assert all(c["ready"] for c in containers)
    return {
        "uid": pods[0]["metadata"]["uid"],
        "containers": [(c["name"], c["restartCount"], c["imageID"]) for c in containers],
        "spec": deployment["spec"], "generation": deployment["metadata"]["generation"],
    }


def analyze(root):
    manifest = read_json(root / "manifest.json")
    assert manifest["status"] == "complete", "Incomplete series"
    assert manifest["order"] == ["off", "on", "on", "off", "on", "off", "off", "on"]
    assert len(manifest["runs"]) == 8
    project = root.parents[1]
    for relative, key in (("bench/observe.py", "observer_sha256"), ("bench/inference.js", "load_script_sha256")):
        frozen = root / "sources" / Path(relative).name
        source = frozen if frozen.is_file() else project / relative
        actual = hashlib.sha256(source.read_bytes()).hexdigest().upper()
        assert actual == manifest[key], f"Source changed: {relative}"

    runs = []
    identity = None
    token_lengths = set()
    for index, info in enumerate(manifest["runs"], 1):
        assert info["index"] == index and info["mode"] == manifest["order"][index - 1]
        assert info["pair"] == (index - 1) // 2 + 1
        assert info["load_exit_code"] == 0 and info["cluster_unchanged"]
        folder = root / info["directory"]
        assert read_json(folder / "metadata.json") == info
        for name in ("cluster-before.json", "cluster-after.json"):
            state = snapshot_identity(folder / name)
            if identity is None:
                identity = state
            assert state == identity, f"Cluster changed in {folder.name}"
        metrics = read_json(folder / "summary.json")["metrics"]
        points = [json.loads(line) for line in (folder / "requests.json").read_text(encoding="utf-8").splitlines()]
        def samples(metric):
            return [p["data"]["value"] for p in points if p.get("type") == "Point" and p.get("metric") == metric]
        latencies = samples("successful_latency_ms")
        errors = samples("inference_errors")
        assert 24 <= len(latencies) <= 25
        assert len(latencies) == len(errors) == metrics["iterations"]["count"]
        assert sum(errors) == 0 and metrics["inference_errors"]["value"] == 0
        assert metrics["dropped_iterations"]["count"] == 0
        average = statistics.mean(latencies)
        p95 = percentile(latencies, .95)
        assert math.isclose(average, metrics["successful_latency_ms"]["avg"])
        assert math.isclose(p95, metrics["successful_latency_ms"]["p(95)"])
        tokens = samples("output_tokens")
        assert len(tokens) == len(latencies)
        token_lengths.update(tokens)
        begin = datetime.fromisoformat(info["load_started_at_utc"])
        end = datetime.fromisoformat(info["load_finished_at_utc"])
        assert (end - begin).total_seconds() >= 120
        count = 0
        errors_count = 0
        if info["mode"] == "on":
            assert info["observer_exit_code"] == 0
            observations = [json.loads(line) for line in (folder / "cluster.jsonl").read_text(encoding="utf-8").splitlines()]
            count = len(observations)
            assert count >= 140 / manifest["observer_interval_seconds"]
            errors_count = sum(len(o["errors"]) for o in observations)
            assert errors_count == 0
            starts = [datetime.fromisoformat(o["time"]) for o in observations]
            assert all(t.utcoffset() is not None for t in starts), "Observer times must include a timezone"
            intervals = [(later - earlier).total_seconds() for earlier, later in zip(starts, starts[1:])]
            assert all(gap > 0 for gap in intervals), "Observer times must be strictly increasing without duplicates"
            maximum_gap = 2 * manifest["observer_interval_seconds"]
            assert all(gap <= maximum_gap for gap in intervals), "Observer collection gap exceeds two polling intervals"
            assert starts[0] <= begin and starts[-1] >= end, "Observer does not cover the whole run"
            assert all(len(o["pods"]["items"]) == 1 for o in observations)
            assert all(o["pods"]["items"][0]["metadata"]["uid"] == identity["uid"] for o in observations)
            assert all(o["hpa"]["items"] == [] for o in observations)
        else:
            assert not (folder / "cluster.jsonl").exists(), "Control run contains observer data"
        runs.append({"index": index, "pair": info["pair"], "mode": info["mode"],
                     "requests": len(latencies), "mean_ms": average, "p95_ms": p95,
                     "max_ms": max(latencies), "errors": 0, "dropped": 0,
                     "observer_samples": count, "collection_errors": errors_count})
    assert len(token_lengths) == 1, "Output lengths changed between conditions"

    pairs = []
    for pair in range(1, 5):
        group = [r for r in runs if r["pair"] == pair]
        off = next(r for r in group if r["mode"] == "off")
        on = next(r for r in group if r["mode"] == "on")
        pairs.append({"pair": pair, "order": "/".join(r["mode"] for r in group),
                      "off_mean_ms": off["mean_ms"], "on_mean_ms": on["mean_ms"],
                      "mean_change_percent": (on["mean_ms"] / off["mean_ms"] - 1) * 100,
                      "off_p95_ms": off["p95_ms"], "on_p95_ms": on["p95_ms"],
                      "p95_change_percent": (on["p95_ms"] / off["p95_ms"] - 1) * 100})
    mean_changes = [p["mean_change_percent"] for p in pairs]
    p95_changes = [p["p95_change_percent"] for p in pairs]
    median_mean = statistics.median(mean_changes)
    median_p95 = statistics.median(p95_changes)
    passed = (median_mean <= manifest["mean_budget_percent"]
              and median_p95 <= manifest["p95_budget_percent"]
              and max(mean_changes) <= manifest["maximum_pair_mean_percent"])
    analysis = {
        "source_hashes_match": True, "cluster_unchanged": True,
        "total_requests": sum(r["requests"] for r in runs), "pairs": pairs, "runs": runs,
        "output_tokens": list(token_lengths),
        "median_paired_mean_change_percent": median_mean,
        "median_paired_p95_change_percent": median_p95,
        "pair_mean_change_range_percent": [min(mean_changes), max(mean_changes)],
        "pair_p95_change_range_percent": [min(p95_changes), max(p95_changes)],
        "positive_mean_pairs": sum(p > 0 for p in mean_changes),
        "provisional_budget_met": passed,
        "interpretation": "Engineering screening only; four pairs do not establish general equivalence.",
    }
    for filename, records in (("runs.csv", runs), ("pairs.csv", pairs)):
        with (root / filename).open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    (root / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    return analysis


if __name__ == "__main__":
    result = analyze(Path(sys.argv[1]).resolve())
    print(json.dumps(result, indent=2))
    print("PASS: artifacts verified (budget decision is recorded separately)")

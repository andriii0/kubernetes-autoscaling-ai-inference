"""Summarize saved pilot runs and plot aligned observations without changing raw files."""
import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

from pilot_records import read_jsonl, reconcile, timestamp


def percentile(values, fraction):
    """Linear interpolation at (n - 1) * fraction, matching the k6 trend summary."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def load_results(folder):
    folder = folder.resolve()
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    return {"folder": folder, "metadata": metadata, "check": reconcile(folder, metadata),
            "events": list(read_jsonl(folder / "request-events.jsonl")),
            "cluster": list(read_jsonl(folder / "cluster.jsonl")),
            "dropped": [p["data"] for p in read_jsonl(folder / "requests.json")
                        if p.get("type") == "Point" and p.get("metric") == "dropped_iterations" and p["data"]["value"] > 0]}


def resource_points(data):
    """Keep source timestamps and missing rates; select the intended container only."""
    metadata = data["metadata"]
    points = []
    for sample in data["cluster"]:
        matches = [r for r in sample["resource_usage"] if r["scope"] == "container"
                   and r.get("namespace") == metadata["namespace"] and r["container"] == metadata["container"]
                   and r["pod_uid"] == metadata["initial_identity"]["pod_uid"]]
        record = matches[0] if len(matches) == 1 else {}
        collected = timestamp(sample["time"])
        points.append({"collected": collected,
                       "cpu_time": record["cpu_timestamp_ms"] / 1000 if record.get("cpu_timestamp_ms") is not None else collected,
                       "memory_time": record["memory_timestamp_ms"] / 1000 if record.get("memory_timestamp_ms") is not None else collected,
                       "cpu": record.get("cpu_cores"), "memory": record.get("memory_working_set_bytes"),
                       "errors": len(sample["errors"]),
                       "ready": sum(any(c["type"] == "Ready" and c["status"] == "True"
                                        for c in p.get("status", {}).get("conditions", []))
                                    for p in sample["pods"]["items"]) if sample.get("pods") is not None else None})
    return points


def calculate_metrics(data):
    metadata, check = data["metadata"], data["check"]
    window = check["load_window"]
    if window is None:
        raise ValueError("cannot summarize a run without a usable measured interval")
    beginning = timestamp(window["started_at_utc"])
    ending = timestamp(window["client_drain_end_at_utc"])
    completed = [e for e in data["events"] if e["event"] == "completed"]
    successful = [e for e in completed if e["outcome"] == "success"]
    latency = [e["duration_ms"] for e in successful]
    tokens = [e["output_tokens"] for e in successful if e["output_tokens"] is not None]
    points = resource_points(data)
    measured = [p for p in points if beginning <= p["collected"] <= ending]
    cpu = [p["cpu"] for p in points if beginning <= p["cpu_time"] <= ending and p["cpu"] is not None]
    memory = [p["memory"] for p in points if beginning <= p["memory_time"] <= ending and p["memory"] is not None]
    counts = check["counts"]
    return {"run": data["folder"].name, "run_id": metadata["run_id"], "collection_valid": check["valid"],
            "requested_per_10s": metadata["rate"], "scheduled_seconds": metadata["duration_seconds"],
            "client_window_seconds": ending - beginning,
            **counts, "started_per_second": counts["started"] / metadata["duration_seconds"],
            "completed_per_second": counts["completed"] / (ending - beginning),
            "mean_ms": statistics.mean(latency) if latency else None,
            "p50_ms": percentile(latency, .5), "p95_ms": percentile(latency, .95),
            "max_ms": max(latency, default=None), "token_samples": len(tokens),
            "tokens_min": min(tokens, default=None), "tokens_p50": percentile(tokens, .5),
            "tokens_max": max(tokens, default=None), "observations_in_load": len(measured),
            "cpu_valid_samples": len(cpu), "cpu_mean_cores": statistics.mean(cpu) if cpu else None,
            "peak_memory_mib": max(memory) / 2**20 if memory else None,
            "observation_max_gap_seconds": check.get("observation", {}).get("max_gap_seconds"),
            "collection_errors": check.get("observation", {}).get("collection_errors"),
            "collection_error_details": "; ".join(check["errors"]), "warnings": "; ".join(check["warnings"])}


def create_plots(data, row, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    start = timestamp(data["check"]["load_window"]["started_at_utc"])
    duration = row["scheduled_seconds"]
    points = resource_points(data)
    completed = [e for e in data["events"] if e["event"] == "completed"]
    colors = {"success": "#2463a2", "failure": "#bd5b26"}
    fig, axes = plt.subplots(5, 1, figsize=(11, 12), sharex=True, layout="constrained")
    for outcome in ("success", "failure"):
        events = [e for e in completed if e["outcome"] == outcome]
        if events:
            axes[0].scatter([timestamp(e["finished_at_utc"]) - start for e in events],
                            [e["duration_ms"] / 1000 for e in events], s=18,
                            marker="o" if outcome == "success" else "x", color=colors[outcome], label=outcome)
    axes[0].set_ylabel("Response time (s)")
    axes[0].legend(loc="upper left", fontsize=9)
    p95 = "missing" if row["p95_ms"] is None else f"{row['p95_ms'] / 1000:.3f} s"
    axes[0].set_title(f"{row['run']} | {row['requested_per_10s']} requests / 10 s | "
                      f"successful n={row['successful']}, whole-run p95={p95}", fontsize=11, loc="left")

    # Zero is meaningful for event counts inside a complete ten-second bucket.
    last = max([duration] + [timestamp(e["finished_at_utc"]) - start for e in completed])
    buckets = range(max(1, math.floor(last / 10) + 1))
    histogram = {outcome: Counter(math.floor((timestamp(e["finished_at_utc"]) - start) / 10)
                                 for e in completed if e["outcome"] == outcome)
                 for outcome in ("success", "failure")}
    for outcome in ("success", "failure"):
        counts = histogram[outcome]
        axes[1].bar([i * 10 for i in buckets], [counts[i] for i in buckets], width=4,
                    align="edge", color=colors[outcome], alpha=.8,
                    label=outcome, bottom=[0] * len(buckets) if outcome == "success" else
                    [histogram["success"][i] for i in buckets])
    if data["dropped"]:
        dropped = Counter()
        for point in data["dropped"]:
            dropped[math.floor((timestamp(point["time"]) - start) / 10)] += point["value"]
        axes[1].scatter([i * 10 + 2 for i in dropped], list(dropped.values()), marker="x", color="#222222", label="dropped starts")
    axes[1].set_ylabel("Completed / 10 s")
    axes[1].legend(loc="upper left", fontsize=9)
    axes[2].plot([p["cpu_time"] - start for p in points],
                 [p["cpu"] if p["cpu"] is not None else math.nan for p in points],
                 color="#2463a2", marker="o", markersize=3, linewidth=1)
    axes[2].set_ylabel("Container CPU (cores)")
    axes[3].plot([p["memory_time"] - start for p in points],
                 [p["memory"] / 2**20 if p["memory"] is not None else math.nan for p in points], color="#2463a2", linewidth=1.5)
    axes[3].set_ylabel("Working set (MiB)")
    axes[4].step([p["collected"] - start for p in points],
                 [p["ready"] if p["ready"] is not None else math.nan for p in points], where="post", color="#2463a2")
    axes[4].set_ylabel("Ready replicas")
    axes[4].set_xlabel("Seconds from k6 scenario start; shaded area = scheduled load")
    axes[4].set_yticks(range(max(1, max((p["ready"] or 0 for p in points), default=0)) + 1))
    for ax in axes:
        ax.axvspan(0, duration, color="#dddddd", alpha=.25, zorder=-1)
        ax.axvline(0, color="#777777", linestyle="--", linewidth=.8)
        ax.axvline(duration, color="#777777", linestyle="--", linewidth=.8)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color="#e3e3e3", linewidth=.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(destination.with_suffix(".png"), dpi=150)
    fig.savefig(destination.with_suffix(".svg"))
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--no-plots", action="store_true", help="Only CSV/JSON, without optional Matplotlib")
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        parser.error("output directory already exists; choose a new path")
    try:
        datasets = [load_results(folder) for folder in args.run_dirs]
        rows = [calculate_metrics(data) for data in datasets]
        args.output_dir.mkdir(parents=True, exist_ok=False)
        with (args.output_dir / "summary.csv").open("x", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        (args.output_dir / "analysis.json").write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        for index, (data, row) in enumerate(zip(datasets, rows), 1):
            if not args.no_plots:
                create_plots(data, row, args.output_dir / f"{index:02d}-{row['run']}")
        (args.output_dir / "README.md").write_text(
            "# Pilot analysis\n\nSource folders:\n" + "".join(f"- {d['folder']}\n" for d in datasets) +
            "\nSuccessful latency percentiles use linear interpolation at (n-1)*p; errors are excluded from latency "
            "but counted separately. Failure counts are part of completed requests. Dropped iterations never started. "
            "Resource summaries use source timestamps within the scenario-start to client-drain interval; idle/warmup "
            "and post-load samples remain visible in plots. CPU mean is the arithmetic mean of available source-interval "
            "averages, not integrated CPU consumption. Missing rates remain gaps, and CSV missing values are empty. "
            "Counts are ten-second buckets; the last bucket can be partial. Whole-run p95 is shown with its sample count. "
            "Collection failures remain explicit in the summary; those runs do not establish capacity.\n",
            encoding="utf-8")
        print(f"Saved {len(rows)} run summaries to {args.output_dir}")
        return 0
    except (OSError, ValueError, KeyError, ImportError) as error:
        print(f"Analysis failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

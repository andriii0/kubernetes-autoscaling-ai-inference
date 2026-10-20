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


def identities(data):
    if data["metadata"].get("mode") == "autoscaling":
        return [{"pod_uid": uid} for uid in sorted({p["metadata"]["uid"] for s in data["cluster"] for p in s["pods"]["items"]})]
    original = data["metadata"]["initial_identity"]
    return original if isinstance(original, list) else [original]


def scaling_details(data):
    """Preserve observations and phase assignments rather than infer unavailable controller decisions."""
    from autoscaling import ready, target_hpa
    start = timestamp(data["check"]["load_window"]["started_at_utc"])
    stages, offset = [], 0
    completions = [e for e in data["events"] if e["event"] == "completed"]
    for stage in data["metadata"]["burst_stages"]:
        end = offset + stage["seconds"]
        # Match the validator's one-millisecond boundary allowance without changing raw times.
        events = []
        for event in completions:
            elapsed_ms = round((timestamp(event["started_at_utc"]) - start) * 1000)
            within = round(offset * 1000) <= elapsed_ms < round(end * 1000)
            first_tick = offset == 0 and elapsed_ms == -1
            last_tick = stage is data["metadata"]["burst_stages"][-1] and round(end * 1000) <= elapsed_ms <= round(end * 1000) + 1
            if within or first_tick or last_tick:
                events.append(event)
        good = [e["duration_ms"] for e in events if e["outcome"] == "success"]
        stages.append({**stage, "start_seconds": offset, "end_seconds": end, "assignment": "request start time",
                       "completed": len(events), "successful": len(good), "failed": len(events) - len(good),
                       "p95_ms": percentile(good, .95), "mean_ms": statistics.mean(good) if good else None,
                       "failure_categories": dict(Counter(e["error_category"] for e in events if e["outcome"] == "failure"))})
        offset = end
    pods, timeline = {}, []
    for sample in data["cluster"]:
        hpa = target_hpa(sample, data["metadata"]["deployment"])
        status = hpa.get("status", {}) if hpa else {}
        selected = sample["pods"]["items"]
        timeline.append({"time": sample["time"], "seconds": timestamp(sample["time"]) - start,
                         "ready": sum(ready(p) for p in selected),
                         "running": sum(p.get("status", {}).get("phase") == "Running" and not p["metadata"].get("deletionTimestamp") for p in selected),
                         "desired": status.get("desiredReplicas"), "current": status.get("currentReplicas"),
                         "cpu_metrics": status.get("currentMetrics"), "conditions": status.get("conditions"),
                         "last_scale_time": status.get("lastScaleTime"),
                         "terminating": sum(bool(p["metadata"].get("deletionTimestamp")) for p in selected)})
        present = set()
        for pod in selected:
            uid = pod["metadata"]["uid"]
            present.add(uid)
            row = pods.setdefault(uid, {"name": pod["metadata"]["name"], "created_at_utc": pod["metadata"].get("creationTimestamp"),
                                       "first_seen_at_utc": sample["time"], "last_seen_at_utc": None,
                                       "ready_at_utc": None, "deletion_timestamp_at_utc": None, "deletion_first_observed_at_utc": None, "first_absent_at_utc": None})
            row["last_seen_at_utc"] = sample["time"]
            if ready(pod) and row["ready_at_utc"] is None:
                row["ready_at_utc"] = next(c.get("lastTransitionTime", sample["time"]) for c in pod["status"]["conditions"] if c["type"] == "Ready")
            if pod["metadata"].get("deletionTimestamp"):
                row["deletion_timestamp_at_utc"] = pod["metadata"]["deletionTimestamp"]
                if row["deletion_first_observed_at_utc"] is None:
                    row["deletion_first_observed_at_utc"] = sample["time"]
        for uid, row in pods.items():
            if uid not in present and row["first_absent_at_utc"] is None:
                row["first_absent_at_utc"] = sample["time"]
    for uid, record in data["check"].get("logs", {}).get("pods", {}).items():
        if uid in pods:
            pods[uid]["first_observed_http_response_at_utc"] = record["first_observed_http_response_at_utc"]
            pods[uid]["http_responses_after_load_start"] = record["http_responses_after_load_start"]
    active = [p for p in timeline if p["seconds"] >= 0 and p["desired"] is not None]
    changes = []
    previous_desired = 1
    for point in active:
        desired = point['desired']
        if desired != previous_desired:
            direction = 'growth' if desired > previous_desired else 'reduction'
            matching = next((p for p in active if p['seconds'] >= point['seconds'] and
                             (p['running'] >= desired if direction == 'growth' else p['running'] <= desired)), None)
            changes.append({'direction': direction, 'from': previous_desired, 'to': desired,
                            'requested_seconds': point['seconds'],
                            'running_matches_seconds': matching['seconds'] if matching else None})
        previous_desired = desired
    growth = next((p for p in changes if p['direction'] == 'growth'), None)
    reduction = next((p for p in changes if p['direction'] == 'reduction'), None)
    return {"stages": stages, "timeline": timeline, "pods": pods,
            "changes": changes, "growth_observed": any(p["direction"] == "growth" and p["running_matches_seconds"] is not None for p in changes),
            "reduction_observed": any(p["direction"] == "reduction" and p["running_matches_seconds"] is not None for p in changes),
            "first_growth_seconds": growth["requested_seconds"] if growth else None,
            "first_reduction_seconds": reduction["requested_seconds"] if reduction else None,
            "post_load_no_new_requests_at_utc": next((p["started_at_utc"] for p in data["metadata"]["phases"] if p["phase"] == "post_load_no_new_requests"), None),
            "limitation": "Sampled state, not an exact controller-decision trace; first HTTP response does not prove semantic success."}


def resource_points(data, pod_uid=None):
    """Keep source timestamps and missing rates; select the intended container only."""
    metadata = data["metadata"]
    points = []
    uids = {i["pod_uid"] for i in identities(data)}
    if pod_uid is not None:
        uids = {pod_uid}
    for sample in data["cluster"]:
        if metadata.get("mode") == "autoscaling" and pod_uid is None:
            # The active set changes; totals require a separate synchronized accounting method.
            selected_uids = set()
        else:
            selected_uids = uids
        matches = [r for r in sample["resource_usage"] if r["scope"] == "container"
                   and r.get("namespace") == metadata["namespace"] and r["container"] == metadata["container"]
                   and r["pod_uid"] in selected_uids]
        record = matches[0] if len(matches) == 1 and len(uids) == 1 else {}
        if len(uids) > 1 and len(matches) == len(uids) and {r["pod_uid"] for r in matches} == uids:
            record = {}
            for value, clock in (("cpu_cores", "cpu_timestamp_ms"),
                                 ("memory_working_set_bytes", "memory_timestamp_ms")):
                clocks = {r.get(clock) for r in matches}
                # Sum only a complete set from the same source instant; asynchronous values stay gaps.
                if len(clocks) == 1 and None not in clocks:
                    record[clock] = clocks.pop()
                    record[value] = sum(r[value] for r in matches) if all(r.get(value) is not None for r in matches) else None
        collected = timestamp(sample["time"])
        points.append({"collected": collected,
                       "cpu_time": record["cpu_timestamp_ms"] / 1000 if record.get("cpu_timestamp_ms") is not None else collected,
                       "memory_time": record["memory_timestamp_ms"] / 1000 if record.get("memory_timestamp_ms") is not None else collected,
                       "cpu": record.get("cpu_cores"), "memory": record.get("memory_working_set_bytes"),
                       "errors": len(sample["errors"]),
                       "ready": sum(not p.get("metadata", {}).get("deletionTimestamp") and any(c["type"] == "Ready" and c["status"] == "True"
                                        for c in p.get("status", {}).get("conditions", []))
                                    for p in sample["pods"]["items"]) if sample.get("pods") is not None else None})
    return points


def calculate_metrics(data):
    """Report starts over scheduled load and completions over load plus client drain."""
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


def replica_resources(data):
    """Summarize each replica at its own source timestamps, without adding asynchronous rates."""
    beginning = timestamp(data["check"]["load_window"]["started_at_utc"])
    ending = timestamp(data["check"]["load_window"]["client_drain_end_at_utc"])
    result = {}
    for identity in identities(data):
        points = resource_points(data, identity["pod_uid"])
        cpu = [p["cpu"] for p in points if beginning <= p["cpu_time"] <= ending and p["cpu"] is not None]
        memory = [p["memory"] for p in points if beginning <= p["memory_time"] <= ending and p["memory"] is not None]
        result[identity["pod_uid"]] = {"cpu_valid_samples": len(cpu),
                                       "cpu_mean_cores": statistics.mean(cpu) if cpu else None,
                                       "peak_memory_mib": max(memory) / 2**20 if memory else None}
    return result


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
    rate_label = (f"{data['metadata']['low_rate']} -> {row['requested_per_10s']} -> {data['metadata']['low_rate']}"
                  if data['metadata'].get('profile') == 'burst' else str(row['requested_per_10s']))
    axes[0].set_title(f"{row['run']} | {rate_label} requests / 10 s | "
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
    selected_identities = identities(data)
    multiple = isinstance(data["metadata"]["initial_identity"], list) or data["metadata"].get("mode") == "autoscaling"
    series = [(identity["pod_uid"][:8], resource_points(data, identity["pod_uid"]))
              for identity in selected_identities] if multiple else [("container", points)]
    for label, resource in series:
        axes[2].plot([p["cpu_time"] - start for p in resource],
                     [p["cpu"] if p["cpu"] is not None else math.nan for p in resource],
                     marker="o", markersize=3, linewidth=1, label=label)
        axes[3].plot([p["memory_time"] - start for p in resource],
                     [p["memory"] / 2**20 if p["memory"] is not None else math.nan for p in resource],
                     linewidth=1.5, label=label)
    axes[2].set_ylabel("CPU per copy (cores)" if multiple else "Container CPU (cores)")
    axes[3].set_ylabel("Memory per copy (MiB)" if multiple else "Working set (MiB)")
    if multiple:
        axes[2].legend(loc="upper left", fontsize=8)
        axes[3].legend(loc="upper left", fontsize=8)
    axes[4].step([p["collected"] - start for p in points],
                 [p["ready"] if p["ready"] is not None else math.nan for p in points], where="post", color="#2463a2")
    if data["metadata"].get("mode") == "autoscaling":
        detail = scaling_details(data)
        axes[4].lines[0].set_label("Ready")
        axes[4].step([p["seconds"] for p in detail["timeline"]],
                     [p["desired"] if p["desired"] is not None else math.nan for p in detail["timeline"]],
                     where="post", linestyle="--", label="HPA desired")
        axes[4].legend(loc="upper left", fontsize=8)
        for ax in axes:
            for stage in detail["stages"]:
                ax.axvline(stage["start_seconds"], color="#aaaaaa", linestyle=":", linewidth=.7)
            post = detail["post_load_no_new_requests_at_utc"]
            if post:
                ax.axvspan(timestamp(post) - start, timestamp(data["cluster"][-1]["time"]) - start,
                           color="#d7e9d2", alpha=.35, label="No new requests")
        for stage in detail["stages"]:
            if stage['seconds'] > 1:
                label = f"{stage['name']} ({data['metadata']['low_rate'] if stage['target'] == 'low' else row['requested_per_10s']}/10 s)"
                axes[1].text((stage["start_seconds"] + stage["end_seconds"]) / 2, .97, label,
                             transform=axes[1].get_xaxis_transform(), ha="center", va="top", fontsize=8,
                             bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none"})
        if detail['post_load_no_new_requests_at_utc']:
            midpoint = (timestamp(detail['post_load_no_new_requests_at_utc']) + timestamp(data['cluster'][-1]['time'])) / 2 - start
            axes[1].text(midpoint, .97, 'No new requests', transform=axes[1].get_xaxis_transform(),
                         ha='center', va='top', fontsize=8)
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
    if not args.no_plots:
        try:
            import matplotlib
        except ImportError:
            print('Plots require the optional Matplotlib analysis dependency; install it or use --no-plots.', file=sys.stderr)
            return 1
    try:
        datasets = [load_results(folder) for folder in args.run_dirs]
        rows = [calculate_metrics(data) for data in datasets]
        args.output_dir.mkdir(parents=True, exist_ok=False)
        with (args.output_dir / "summary.csv").open("x", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        (args.output_dir / "analysis.json").write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        per_replica = {d["folder"].name: replica_resources(d) for d in datasets
                       if d["metadata"].get("expected_replicas", 1) == 3 or d["metadata"].get("mode") == "autoscaling"}
        if per_replica:
            (args.output_dir / "per-replica-resources.json").write_text(
                json.dumps(per_replica, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        scaling = {d["folder"].name: scaling_details(d) for d in datasets if d["metadata"].get("mode") == "autoscaling"}
        if scaling:
            (args.output_dir / "scaling.json").write_text(json.dumps(scaling, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        for index, (data, row) in enumerate(zip(datasets, rows), 1):
            if not args.no_plots:
                create_plots(data, row, args.output_dir / f"{index:02d}-{row['run']}")
        (args.output_dir / "README.md").write_text(
            "# Pilot analysis\n\nSource folders:\n" + "".join(f"- {d['folder']}\n" for d in datasets) +
            "\nSuccessful latency percentiles use linear interpolation at (n-1)*p; errors are excluded from latency "
            "but counted separately. Failure counts are part of completed requests. Dropped iterations never started. "
            "started_per_second divides starts by scheduled_seconds (the scheduled load duration). "
            "completed_per_second divides completions by client_window_seconds (scheduled load plus any client drain). "
            "These rates use different windows and are not a direct completion ratio. "
            "Resource summaries use source timestamps within the scenario-start to client-drain interval; idle/warmup "
            "and post-load samples remain visible in plots. CPU mean is the arithmetic mean of available source-interval "
            "averages, not integrated CPU consumption. Missing rates remain gaps, and CSV missing values are empty. "
            "Counts are ten-second buckets; the last bucket can be partial. Whole-run p95 is shown with its sample count. "
            "Collection failures remain explicit in the summary; those runs do not establish capacity. "
            "For three copies, plots and per-replica-resources.json use each pod's own source timestamps. "
            "Total resource values stay missing when source timestamps differ; asynchronous rates are not added.\n",
            encoding="utf-8")
        print(f"Saved {len(rows)} run summaries to {args.output_dir}")
        return 0
    except (OSError, ValueError, KeyError, ImportError) as error:
        print(f"Analysis failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

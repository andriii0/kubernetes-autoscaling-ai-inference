"""Assess saved runs and plot aligned observations without changing raw files."""
import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

from records import iso_time, percentile, read_jsonl, timestamp
from pilot_records import reconcile


def phase_results(data):
    metadata = data['metadata']
    start = timestamp(data['check']['load_window']['started_at_utc'])
    stages = metadata.get('burst_stages') or [{'name': 'steady', 'seconds': metadata['duration_seconds'], 'target': 'peak'}]
    completions = [e for e in data['events'] if e['event'] == 'completed']
    result, offset = [], 0
    for index, stage in enumerate(stages):
        end = offset + stage['seconds']
        events = []
        for event in completions:
            elapsed = round((timestamp(event['started_at_utc']) - start) * 1000)
            if (offset * 1000 <= elapsed < end * 1000 or offset == 0 and elapsed == -1 or
                    index == len(stages) - 1 and end * 1000 <= elapsed <= end * 1000 + 1):
                events.append(event)
        values = [e['duration_ms'] for e in events if e['outcome'] == 'success']
        result.append({**stage, 'start_seconds': offset, 'end_seconds': end, 'assignment': 'request start time',
                       'completed': len(events), 'successful': len(values), 'failed': len(events) - len(values),
                       'p95_ms': percentile(values, .95), 'mean_ms': sum(values) / len(values) if values else None,
                       'failure_categories': dict(Counter(e['error_category'] for e in events if e['outcome'] == 'failure'))})
        offset = end
    return result


def system_outcomes(samples, container):
    result = []
    seen = set()
    identities = {}
    for sample in samples:
        for pod in (sample.get('pods') or {}).get('items', []):
            for c in pod.get('status', {}).get('containerStatuses', []):
                if c['name'] != container:
                    continue
                uid = pod['metadata']['uid']
                identity = (c.get('containerID'), c.get('restartCount'))
                if uid in identities and identity != identities[uid]:
                    result.append({'pod_uid': uid, 'identity_before': identities[uid], 'identity_after': identity, 'observed_at_utc': sample['time']})
                identities[uid] = identity
                for state in (c.get('state', {}), c.get('lastState', {})):
                    term = state.get('terminated')
                    if term:
                        key = (pod['metadata']['uid'], c.get('restartCount'), term.get('reason'), term.get('finishedAt'))
                        if key not in seen:
                            seen.add(key)
                            result.append({'pod_uid': key[0], 'restart_count': key[1], 'termination': term})
    return result


def assessment(data):
    metadata, check = data['metadata'], data['check']
    config = metadata['workload']['main_protocol']
    window = check.get('load_window')
    counts = check.get('counts', {})
    valid = bool(check['valid'])
    distribution = check.get('distribution', {})
    if metadata.get('expected_replicas') == 3 and not distribution.get('all_pods_active'):
        valid = False
    primary = None
    if window:
        try:
            primary = next(p for p in phase_results(data) if p['name'] == ('peak' if metadata['profile'] == 'burst' else 'steady'))
        except (ValueError, KeyError, TypeError, StopIteration):
            valid = False
    known = valid and primary is not None and primary['completed'] > 0
    p95 = primary['p95_ms'] if primary else None
    unknown = 'not_assessable'
    p95_pass = p95 <= config['primary_p95_ms'] if known and p95 is not None else unknown
    primary_errors = primary['failed'] / primary['completed'] <= metadata['workload']['thresholds']['error_rate'] if known else unknown
    whole_errors = (counts['failed'] / counts['completed'] <= metadata['workload']['thresholds']['error_rate']
                    if valid and counts.get('completed') else unknown)
    # Process end alone is insufficient: require the normal post-load phase too.
    profile_end = metadata.get('scheduled_profile_finished_at_utc')
    complete = bool(window and profile_end and timestamp(profile_end) >= timestamp(window['scheduled_end_at_utc']) and
                    any(p['phase'] in ('post_load', 'post_load_no_new_requests') for p in metadata['phases']))
    drops = counts.get('dropped')
    overall = unknown
    if valid and complete and drops == 0:
        targets = (p95_pass, primary_errors, whole_errors)
        overall = 'fail' if False in targets else 'pass' if all(t is True for t in targets) else unknown
    scaling = 'not_applicable'
    if metadata['mode'] == 'autoscaling':
        if not data['cluster'] or any(s.get('pods') is None or s.get('hpa') is None for s in data['cluster']):
            scaling = 'unknown'
        elif window:
            try:
                detail = scaling_details(data)
                observed = [name for name in ('growth', 'reduction') if detail[name + '_observed']]
                scaling = '+'.join(observed) or 'no_transition'
            except (ValueError, KeyError, TypeError, StopIteration):
                scaling = 'unknown'
        else:
            scaling = 'unknown'
    return {'protocol_version': metadata['protocol_version'], 'data_valid': valid, 'duration_complete': complete,
            'unfinished': counts.get('unfinished'), 'dropped': drops, 'primary': primary,
            'primary_p95_pass': p95_pass, 'primary_errors_pass': primary_errors,
            'whole_run_errors_pass': whole_errors, 'scaling_observed': scaling, 'overall': overall,
            'sensitivity_p95_pass': p95 <= config['sensitivity_p95_ms'] if known and p95 is not None else unknown,
            'system_outcomes': system_outcomes(data['cluster'], metadata['container']),
            'limitations': check['errors'] + (['not every fixed replica has observed Service traffic']
                if metadata.get('expected_replicas') == 3 and not distribution.get('all_pods_active') else []), 'server_drain_verified': metadata.get('server_drain_verified', False)}


def save_assessment(folder, metadata, check):
    """Also retain a not-assessable record when preparation or collection stops early."""
    def records(name):
        path = folder / name
        if not path.exists():
            return []
        result = []
        try:
            for record in read_jsonl(path):
                result.append(record)
        except (OSError, ValueError):
            pass  # Reconciliation records the failure; retain the readable prefix here.
        return result
    data = {'metadata': metadata, 'check': check, 'events': records('request-events.jsonl'), 'cluster': records('cluster.jsonl')}
    result = assessment(data)
    (folder / 'assessment.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return result


def primary_resources(data):
    """Integrate counter deltas on each source clock, without filling missing intervals."""
    window = data['check'].get('load_window')
    if not window:
        return {'application_cpu_core_seconds_estimate': None, 'instances': [], 'nodes': []}
    start, end = timestamp(window['started_at_utc']), timestamp(window['scheduled_end_at_utc'])
    metadata = data['metadata']
    interval = metadata['observer_interval_seconds']
    instances, previous = {}, {}
    state_complete = True
    for sample in data['cluster']:
        collected = timestamp(sample['time'])
        pods = (sample.get('pods') or {}).get('items', [])
        if sample.get('pods') is None and start <= collected <= end:
            state_complete = False
        # Register expected instances even when all their resource values are missing.
        for pod in pods:
            for status in pod.get('status', {}).get('containerStatuses', []):
                if status['name'] != metadata['container'] or not status.get('containerID'):
                    continue
                key = ('container', pod['metadata']['uid'], status.get('restartCount'))
                state = status.get('state', {})
                details = state.get('running') or state.get('terminated') or {}
                birth = details.get('startedAt')
                death = state.get('terminated', {}).get('finishedAt')
                row = instances.setdefault(key, {'scope': 'container', 'pod_uid': key[1], 'restart_count': key[2],
                    'container_id': status['containerID'], 'active_start': timestamp(birth) if birth else None,
                    'active_end': None, 'present_after_end': False, 'source_start': None,
                    'intervals': [], 'cpu': 0., 'memory': [], 'missing_memory': 0})
                if death:
                    row['active_end'] = timestamp(death)
                if collected >= end and 'running' in state:
                    row['present_after_end'] = True
        available = set()
        for record in sample['resource_usage']:
            scope = record['scope']
            if scope == 'container':
                if record.get('namespace') != metadata['namespace'] or record.get('container') != metadata['container']:
                    continue
                key = (scope, record.get('pod_uid'), record.get('restart_count'))
                if key not in instances:
                    # No state identity: cannot establish an expected lifetime.
                    state_complete = False
                    continue
                row = instances[key]
            elif scope == 'node':
                key = (scope, record['node'])
                row = instances.setdefault(key, {'scope': scope, 'node': record['node'], 'active_start': start,
                    'active_end': end, 'present_after_end': True, 'source_start': None,
                    'intervals': [], 'cpu': 0., 'memory': [], 'missing_memory': 0})
            else:
                continue
            available.add(key)
            source_start = record.get('container_start_time_seconds')
            if scope == 'container' and source_start is not None:
                if row['source_start'] is not None and source_start != row['source_start']:
                    # A changed start with unchanged Kubernetes identity is still a continuity break.
                    row['identity_uncertain'] = True
                    previous.pop(key, None)
                row['source_start'] = source_start
            memory_at = record.get('memory_timestamp_ms')
            memory = record.get('memory_working_set_bytes')
            if memory_at is not None and start <= memory_at / 1000 <= end and memory is not None:
                row['memory'].append((memory_at, memory))
            elif start <= collected <= end:
                row['missing_memory'] += 1
            at, counter = record.get('cpu_timestamp_ms'), record.get('cpu_usage_seconds_total')
            if (sample['errors'] or scope == 'container' and source_start is None or at is None or counter is None or
                    not math.isfinite(counter) or counter < 0):
                previous.pop(key, None)
                continue
            at /= 1000
            # Retain the source high-water mark across gaps. An older point must not
            # become a new baseline and overlap an interval already accumulated.
            if at < row.get('last_cpu_timestamp', -math.inf):
                previous.pop(key, None)
                continue
            row['last_cpu_timestamp'] = at
            old = previous.get(key)
            if old and at == old[0]:
                if counter != old[1]:
                    previous.pop(key, None)
                else:
                    previous[key] = (old[0], old[1], collected)
                continue
            previous[key] = (at, counter, collected)
            if not old or at <= old[0] or counter < old[1] or collected - old[2] > 2 * interval:
                continue
            left, right = max(start, old[0]), min(end, at)
            if right > left:
                row['cpu'] += (counter - old[1]) * (right - left) / (at - old[0])
                row['intervals'].append((left, right))
        # An absent record or failed scrape must break the next counter pair.
        for key in set(previous) - available:
            previous.pop(key, None)
        if start <= collected <= end:
            for key in set(instances) - available:
                row = instances[key]
                if row['active_start'] is None or row['active_start'] <= collected:
                    if row['active_end'] is None or collected <= row['active_end']:
                        row['missing_memory'] += 1
    result = {'window': window, 'method': 'Counter deltas clipped by interval overlap; constant average rate within each source interval.',
              'instances': [], 'nodes': [], 'application_cpu_core_seconds_estimate': None}
    for row in instances.values():
        birth, death = row['active_start'], row['active_end']
        if row['present_after_end'] and death is None:
            death = end
        expected = max(0, min(end, death) - max(start, birth)) if birth is not None and death is not None else None
        # Merge coverage intervals so duplicate/repeated polls cannot inflate coverage.
        merged = []
        for a, b in sorted(row['intervals']):
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        covered = sum(b - a for a, b in merged)
        complete = bool(expected is not None and not row.get('identity_uncertain') and
                        covered >= expected - 1e-6 and (row['scope'] == 'node' or row['source_start'] is not None))
        readings = dict(row['memory'])
        record = {k: row[k] for k in ('scope', 'pod_uid', 'restart_count', 'container_id', 'node') if k in row}
        record.update(active_start_utc=iso_time(birth) if birth is not None else None,
                      active_end_utc=iso_time(death) if death is not None else None,
                      expected_seconds=expected, cpu_covered_seconds=covered,
                      cpu_coverage=covered / expected if expected else None, cpu_full_coverage=complete,
                      cpu_core_seconds_estimate=row['cpu'] if row['intervals'] else None,
                      observed_peak_memory_mib=max(readings.values()) / 2**20 if readings else None,
                      memory_samples=len(readings), memory_missing_polls=row['missing_memory'],
                      memory_first_source_utc=iso_time(min(readings) / 1000) if readings else None,
                      memory_last_source_utc=iso_time(max(readings) / 1000) if readings else None)
        result['instances' if row['scope'] == 'container' else 'nodes'].append(record)
    relevant = [r for r in result['instances'] if r['expected_seconds'] is None or r['expected_seconds'] > 0]
    if state_complete and relevant and all(r['cpu_full_coverage'] for r in relevant):
        result['application_cpu_core_seconds_estimate'] = sum(r['cpu_core_seconds_estimate'] for r in relevant)
    result['application_state_complete'] = state_complete
    return result


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
        uids = {p["metadata"]["uid"] for sample in data["cluster"] if sample.get("pods") is not None
                for p in sample["pods"]["items"]}
        return [{"pod_uid": uid} for uid in sorted(uids)]
    original = data["metadata"]["initial_identity"]
    return original if isinstance(original, list) else [original]


def scaling_details(data):
    """Preserve observations and phase assignments rather than infer unavailable controller decisions."""
    from autoscaling import ready, target_hpa
    start = timestamp(data["check"]["load_window"]["started_at_utc"])
    stages = phase_results(data)
    pods, timeline = {}, []
    for sample in data["cluster"]:
        hpa = target_hpa(sample, data["metadata"]["deployment"]) if sample.get("hpa") is not None else None
        status = hpa.get("status", {}) if hpa else {}
        selected = sample["pods"]["items"] if sample.get("pods") is not None else None
        timeline.append({"time": sample["time"], "seconds": timestamp(sample["time"]) - start,
                         "ready": sum(ready(p) for p in selected) if selected is not None else None,
                         "running": sum(p.get("status", {}).get("phase") == "Running" and not p["metadata"].get("deletionTimestamp") for p in selected) if selected is not None else None,
                         "desired": status.get("desiredReplicas"), "current": status.get("currentReplicas"),
                         "cpu_metrics": status.get("currentMetrics"), "conditions": status.get("conditions"),
                         "last_scale_time": status.get("lastScaleTime"),
                         "terminating": sum(bool(p["metadata"].get("deletionTimestamp")) for p in selected) if selected is not None else None})
        if selected is None:
            # An unavailable snapshot cannot establish pod presence or disappearance.
            continue
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
            matching = next((p for p in active if p['seconds'] >= point['seconds'] and p['running'] is not None and
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
            import matplotlib  # noqa: F401 - check the optional dependency before creating output
        except ImportError:
            print('Plots require the optional Matplotlib analysis dependency; install it or use --no-plots.', file=sys.stderr)
            return 1
    try:
        folders = [folder.resolve() for folder in args.run_dirs]
        names = set()
        for folder in folders:
            if folder.name in names:
                raise ValueError(f'duplicate run folder name {folder.name!r}; analyze these runs separately')
            names.add(folder.name)
        datasets = [load_results(folder) for folder in folders]
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
        main_runs = [d for d in datasets if d['metadata'].get('protocol_version')]
        if main_runs:
            for filename, function in (('assessments.json', assessment), ('primary-resources.json', primary_resources)):
                (args.output_dir / filename).write_text(json.dumps(
                    {d['folder'].name: function(d) for d in main_runs}, indent=2, allow_nan=False) + '\n', encoding='utf-8')
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
            "Total instantaneous resource values stay missing when source timestamps differ; asynchronous rates are not added. "
            "For main runs, assessments.json applies protocol targets to the primary start-time phase; "
            "primary-resources.json integrates source counter intervals over scheduled load only, with coverage. "
            "Node consumption and observed per-instance memory peaks are reported separately.\n",
            encoding="utf-8")
        print(f"Saved {len(rows)} run summaries to {args.output_dir}")
        return 0
    except (OSError, ValueError, KeyError, ImportError) as error:
        print(f"Analysis failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

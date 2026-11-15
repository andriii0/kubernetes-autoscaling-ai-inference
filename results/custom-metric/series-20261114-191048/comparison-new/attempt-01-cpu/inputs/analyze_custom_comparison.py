"""Derived outcomes for the separate CPU/request HPA comparison; no raw writes."""

import math
import statistics

from autoscaling import ready, target_hpa
from records import timestamp, read_jsonl


def capacity(points, start, end, key):
    covered = total = 0.0
    seconds = {str(n): 0.0 for n in range(4)}
    for a, b in zip(points, points[1:]):
        width = b['time'] - a['time']
        left, right = max(start, a['time']), min(end, b['time'])
        value = a[key]
        if right <= left or not 0 < width <= 10 or type(value) is not int or not 0 <= value <= 3:
            continue
        duration = right - left
        covered += duration
        total += value * duration
        seconds[str(value)] += duration
    return {'replica_seconds': total, 'covered_seconds': covered,
            'missing_seconds': max(0, end - start - covered), 'seconds_at_count': seconds,
            'method': 'Previous observed count over intervals <=10s, clipped to window; not CPU consumption.'}


def outcomes(data, folder, policy):
    start = timestamp(data['check']['load_window']['started_at_utc'])
    peak = start + 121
    end = start + 782
    starts = {e['request_id'] for e in data['events'] if e['event'] == 'started'
              and 121000 <= round((timestamp(e['started_at_utc']) - start) * 1000) < 421000}
    completed = [e for e in data['events'] if e['event'] == 'completed' and e['request_id'] in starts]
    ontime = sum(e['outcome'] == 'success' and e['duration_ms'] <= 5000 for e in completed)
    failures = sum(e['outcome'] == 'failure' for e in completed)
    points, signal_events = [], {2: None, 3: None}
    for sample in data['cluster']:
        hpa = target_hpa(sample, 'ollama')
        if not hpa:
            continue
        status = hpa.get('status', {})
        at = timestamp(sample['time'])
        points.append({'time': at, 'desired': status.get('desiredReplicas'),
                       'ready': sum(ready(p) for p in sample['pods']['items'])})
        if policy == 'cpu':
            metric = next((m['resource'].get('current', {}).get('averageUtilization')
                           for m in status.get('currentMetrics', [])
                           if m.get('type') == 'Resource' and m['resource'].get('name') == 'cpu'), None)
            replicas = status.get('currentReplicas')
            if isinstance(metric, (int, float)) and type(replicas) is int and metric >= 0:
                demand = math.ceil(replicas * metric / 60)
                for n in (2, 3):
                    if demand >= n and at <= end and signal_events[n] is None:
                        signal_events[n] = at - peak
    if policy == 'active-1':
        for row in read_jsonl(folder / 'custom-metric.jsonl'):
            signal = row.get('signal')
            if signal:
                for n in (2, 3):
                    if signal['active_requests'] >= n and signal['received_at'] <= end and signal_events[n] is None:
                        signal_events[n] = signal['received_at'] - peak
    reaction = {}
    for n in (2, 3):
        reaction[str(n)] = {'signal_at_seconds_from_peak': signal_events[n], **{
            key + '_at_seconds_from_peak': next((p['time'] - peak for p in points
                  if p['time'] <= end and isinstance(p[key], int) and p[key] >= n), None)
            for key in ('desired', 'ready')}}
    post = next(p for p in data['metadata']['phases'] if p['phase'] == 'post_load_no_new_requests')
    post_start = timestamp(post['started_at_utc'])
    post_end = post_start + data['metadata']['post_seconds']
    return {'peak_started': len(starts), 'peak_on_time_successes': ontime,
            'peak_on_time_fraction': ontime / len(starts) if starts else None,
            'peak_error_fraction': failures / len(starts) if starts else None,
            'peak_unfinished': len(starts) - len(completed), 'dropped_starts': data['check']['counts']['dropped'],
            'capacity': {window: {key: capacity(points, a, b, key) for key in ('desired', 'ready')}
                         for window, a, b in (('load', start, end), ('post_load', post_start, post_end))},
            'reaction': reaction,
            'timing_scope': 'Observed bounds; CPU demand uses HPA-reported utilization/current replicas, request demand uses total gateway gauge. Controller tolerance/readiness rules can change actual decisions. Ready is not model-warm.'}


def summarize(rows):
    if len(rows) != 6 or sorted((r['pair'], r['policy']) for r in rows) != [
            (p, policy) for p in (1, 2, 3) for policy in ('active-1', 'cpu')]:
        raise ValueError('summary requires exactly three complete CPU/request pairs')
    pairs = []
    for pair in (1, 2, 3):
        cpu = next(r for r in rows if r['pair'] == pair and r['policy'] == 'cpu')['outcomes']
        custom = next(r for r in rows if r['pair'] == pair and r['policy'] == 'active-1')['outcomes']
        pairs.append({'pair': pair,
                      'on_time_fraction_difference': custom['peak_on_time_fraction'] - cpu['peak_on_time_fraction'],
                      'error_fraction_difference': custom['peak_error_fraction'] - cpu['peak_error_fraction']})
    arms = {}
    for policy in ('cpu', 'active-1'):
        selected = [r for r in rows if r['policy'] == policy]
        values = {'peak_on_time_fraction': [r['outcomes']['peak_on_time_fraction'] for r in selected],
                  'peak_error_fraction': [r['outcomes']['peak_error_fraction'] for r in selected],
                  'successful_peak_p95_ms': [r['assessment']['primary']['p95_ms'] for r in selected]}
        arms[policy] = {key: {'values': nums, 'median': statistics.median(nums), 'min': min(nums), 'max': max(nums)}
                        if all(n is not None for n in nums) else {'values': nums, 'median': None, 'min': None, 'max': None}
                        for key, nums in values.items()}
    return {'pairs': pairs, 'arms': arms, 'consistent_service_improvement': all(
        p['on_time_fraction_difference'] > 0 and p['error_fraction_difference'] <= 0 for p in pairs),
        'scope': 'Three descriptive pairs, not statistical significance or measured resource-cost savings.'}

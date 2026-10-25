"""Preparation and assessment rules for the agreed main series, using existing records."""

import json
import math
import re
import subprocess
import time

from pilot_records import iso_time, percentile, pilot_identity, read_jsonl, timestamp


def matrix():
    rows = []
    for repetition, modes, profiles in (
        (1, ('fixed-1', 'fixed-3', 'autoscaling'), ('steady', 'burst')),
        (2, ('fixed-3', 'autoscaling', 'fixed-1'), ('burst', 'steady')),
        (3, ('autoscaling', 'fixed-1', 'fixed-3'), ('steady', 'burst')),
    ):
        for profile in profiles:
            for mode in modes:
                rows.append(dict(planned_order=len(rows) + 1, repetition=repetition, mode=mode, profile=profile))
    return rows


def validate_arguments(args, workload, seconds):
    """Reject conflicting main settings before creating an attempt folder."""
    if not args.protocol_version:
        if any(value is not None for value in (args.repetition, args.planned_order, args.actual_order, args.replaces_run)):
            raise ValueError('main-series metadata requires --protocol-version')
        return
    config = workload['main_protocol']
    if args.protocol_version != config['version']:
        raise ValueError('unsupported main protocol version')
    expected = next((r for r in matrix() if r['planned_order'] == args.planned_order), None)
    if expected is None or any(getattr(args, k) != expected[k] for k in ('mode', 'profile', 'repetition')):
        raise ValueError('repetition, mode and profile must match --planned-order in the matrix')
    if args.actual_order is None or args.actual_order < 1:
        raise ValueError('--actual-order must be a positive attempt number')
    checks = {'rate': config['peak_rate'], 'low_rate': config['low_rate'],
              'observer_interval': config['observer_interval_seconds'], 'idle_seconds': config['idle_seconds'],
              'warmup_timeout': config['warmup_timeout_seconds'],
              'post_seconds': config['hpa_post_seconds'] if args.mode == 'autoscaling' else config['fixed_post_seconds']}
    if any(getattr(args, k) != value for k, value in checks.items()):
        raise ValueError('main arguments conflict with frozen workload.json settings')
    if args.slo_ms is not None and args.slo_ms != config['primary_p95_ms']:
        raise ValueError('main latency target is fixed in workload.json; omit --slo-ms')
    expected_seconds = config['steady_seconds'] if args.profile == 'steady' else sum(s['seconds'] for s in workload['burst_stages'])
    if seconds != expected_seconds:
        raise ValueError('main duration conflicts with the protocol')
    if (args.context, args.namespace, args.selector, args.deployment, args.container, args.service) != (
            'ai-lab', 'inference', 'app=ollama', 'ollama', 'ollama', 'ollama'):
        raise ValueError('main protocol requires the agreed ai-lab/inference/ollama workload')


def source_revision(root):
    def git(*args):
        return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    return {'commit': git('rev-parse', 'HEAD'), 'dirty': bool(git('status', '--porcelain'))}


def prepare_fixed(observer, deployment, container, replicas):
    """Select the requested fixed mode after recovery; do not restart the workload."""
    hpas = json.loads(observer.read('-n', observer.namespace, 'get', 'hpa', '-o', 'json'))['items']
    for hpa in hpas:
        target = hpa['spec']['scaleTargetRef']
        ours = target.get('kind') == 'Deployment' and target.get('name') == deployment
        if ours and hpa['metadata']['name'] != 'ollama' or hpa['metadata']['name'] == 'ollama' and not ours:
            raise ValueError('another HPA conflicts with fixed-mode preparation')
    observer.read('-n', observer.namespace, 'delete', 'hpa', 'ollama', '--ignore-not-found')
    observer.read('-n', observer.namespace, 'scale', f'deployment/{deployment}', f'--replicas={replicas}')
    deadline, last = time.monotonic() + 180, None
    while time.monotonic() < deadline:
        sample = observer.collect(5)
        try:
            pilot_identity(sample, deployment, container, replicas)
            return
        except (ValueError, KeyError, TypeError) as error:
            last = str(error)
        time.sleep(2)
    raise RuntimeError(f'initial fixed state did not settle within 180 seconds: {last}')


def cpu_quantity(value):
    match = re.fullmatch(r'(\d+(?:\.\d+)?)(n|u|m)?', value)
    if not match:
        raise ValueError('unrecognized metrics-server CPU quantity')
    return float(match[1]) * {None: 1, 'm': 1e-3, 'u': 1e-6, 'n': 1e-9}[match[2]]


def metrics_window_seconds(value):
    # Kubernetes durations may include several units, such as 30s or 1m0s.
    parts = re.findall(r'(\d+(?:\.\d+)?)(ns|us|ms|s|m|h)', value)
    if not parts or ''.join(n + u for n, u in parts) != value:
        raise ValueError('unrecognized metrics-server window')
    return sum(float(n) * {'ns': 1e-9, 'us': 1e-6, 'ms': .001, 's': 1, 'm': 60, 'h': 3600}[u] for n, u in parts)


class QuietState:
    """Two fresh low-CPU source intervals for the same initial container instances."""

    def __init__(self, identities, container, after, limit=.1):
        self.uids = {i['pod_uid'] for i in (identities if isinstance(identities, list) else [identities])}
        self.container, self.after, self.limit = container, after, limit
        self.previous, self.consecutive = {}, 0
        self.low_intervals = dict.fromkeys(self.uids, 0)
        self.last_sample = None

    def accept(self, sample, require_metrics=False):
        collected = timestamp(sample['time'])
        if self.last_sample is not None and collected - self.last_sample > 10:
            self.previous.clear()
            self.low_intervals = dict.fromkeys(self.uids, 0)
        self.last_sample = collected
        records = {r['pod_uid']: r for r in sample['resource_usage'] if r['scope'] == 'container'
                   and r.get('pod_uid') in self.uids and r['container'] == self.container}
        if sample['errors']:
            self.previous.clear()
            self.low_intervals = dict.fromkeys(self.uids, 0)
            self.consecutive = 0
            return False
        for uid in self.uids:
            r = records.get(uid, {})
            point = (r.get('cpu_timestamp_ms'), r.get('cpu_usage_seconds_total'), r.get('restart_count'),
                     r.get('container_start_time_seconds'))
            old = self.previous.get(uid)
            if point[0] is None or point[1] is None or not all(math.isfinite(v) for v in point[:2]):
                self.previous.pop(uid, None)
                self.low_intervals[uid] = 0
                continue
            if old and point[0] <= old[0]:
                if point != old:
                    self.previous.pop(uid, None)
                    self.low_intervals[uid] = 0
                continue  # Only an unchanged cached point preserves progress.
            self.previous[uid] = point
            low = bool(old and point[0] > old[0] and point[2:] == old[2:] and point[1] >= old[1]
                       and old[0] / 1000 >= self.after
                       and (point[1] - old[1]) / ((point[0] - old[0]) / 1000) <= self.limit)
            self.low_intervals[uid] = self.low_intervals[uid] + 1 if low else 0
        self.consecutive = min(self.low_intervals.values())
        if self.consecutive < 2:
            return False
        if require_metrics:
            pods = {p['metadata']['name'] for p in sample['pods']['items'] if p['metadata']['uid'] in self.uids}
            readings = {p['metadata']['name']: p for p in (sample.get('resources') or {}).get('items', [])}
            for pod in pods:
                record = readings.get(pod)
                if record is None:
                    return False
                end = timestamp(record['timestamp'])
                if end - metrics_window_seconds(record['window']) < self.after:
                    return False
                containers = [c for c in record['containers'] if c['name'] == self.container]
                if len(containers) != 1 or cpu_quantity(containers[0]['usage']['cpu']) > self.limit:
                    return False
        return True


def settle(collection, after, require_metrics=False):
    gate = QuietState(collection.identity, collection.container, timestamp(after))
    deadline = time.monotonic() + 180
    previous = None
    while time.monotonic() < deadline:
        collection.wait(0)
        with collection.lock:
            sample = collection.last
            if sample['time'] != previous:
                previous = sample['time']
                if gate.accept(sample, require_metrics):
                    return {'after_utc': after, 'passed_at_utc': sample['time'],
                            'cpu_limit_cores': gate.limit, 'fresh_low_intervals': gate.consecutive,
                            'metrics_server_window_checked': require_metrics}
        collection.wait(collection.interval)
    raise RuntimeError('quiet-state gate did not pass within 180 seconds; no load started')


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
        from collections import Counter
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
        from analyze import scaling_details
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


def check_configuration(deployment):
    container = next(c for c in deployment['spec']['template']['spec']['containers'] if c['name'] == 'ollama')
    resources = container['resources']
    env = {e['name']: e.get('value') for e in container.get('env', [])}
    if (container['image'] != 'ai-inference:0.1' or
            any(cpu_quantity(resources[k]['cpu']) != 2 for k in ('requests', 'limits')) or
            resources['requests']['memory'] not in ('1Gi', '1024Mi', '1073741824') or
            resources['limits']['memory'] not in ('2Gi', '2048Mi', '2147483648') or
            any(env.get(k) != v for k, v in {'OLLAMA_NUM_PARALLEL': '1', 'OLLAMA_CONTEXT_LENGTH': '1024', 'OLLAMA_KEEP_ALIVE': '-1'}.items())):
        raise ValueError('Deployment differs from the main protocol; inspect image, resources and Ollama settings')
def recover(observer, folder, container):
    """Check remaining copies before changing the mode; preserve recovery observations."""
    from observe import utc_now
    started = utc_now()
    deadline, gate, identity = time.monotonic() + 180, None, None
    with (folder / 'recovery-observations.jsonl').open('x', encoding='utf-8') as output:
        while time.monotonic() < deadline:
            sample = observer.collect(5)
            output.write(json.dumps(sample, allow_nan=False) + '\n')
            output.flush()
            pods = (sample.get('pods') or {}).get('items', [])
            current = []
            for pod in pods:
                status = next((c for c in pod.get('status', {}).get('containerStatuses', []) if c['name'] == container), {})
                if (not status.get('ready') or 'running' not in status.get('state', {}) or
                        pod['metadata'].get('deletionTimestamp')):
                    current = []
                    break
                current.append({'pod_uid': pod['metadata']['uid'], 'container_id': status.get('containerID'),
                                'restart_count': status.get('restartCount')})
            current.sort(key=lambda i: i['pod_uid'])
            if current != identity or sample['errors'] or not current:
                identity = current
                gate = QuietState(identity, container, timestamp(started)) if current else None
            if gate and gate.accept(sample):
                return {'started_at_utc': started, 'passed_at_utc': sample['time'], 'identity': identity}
            time.sleep(5)
    raise RuntimeError('remaining copies did not reach quiet state within 180 seconds')


def runtime_context(observer, pods, folder, model):
    """Record model digests, Docker limits and the Minikube profile independently."""
    from urllib.parse import quote
    models = {}
    for pod in pods:
        name = quote(pod['metadata']['name'], safe='')
        raw = observer.read('get', '--raw', f'/api/v1/namespaces/{observer.namespace}/pods/{name}:11434/proxy/api/tags')
        tags = json.loads(raw)
        selected = [m for m in tags['models'] if m.get('name') == model or m.get('model') == model]
        if len(selected) != 1 or not selected[0].get('digest'):
            raise ValueError('cannot identify the frozen model on every initial copy')
        models[pod['metadata']['uid']] = selected[0]
    if len({m['digest'] for m in models.values()}) != 1:
        raise ValueError('initial copies have different model digests')
    def command(args):
        result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=15)
        return json.loads(result.stdout)
    docker = command(['docker', 'info', '--format', '{"cpu":{{.NCPU}},"memory_bytes":{{.MemTotal}}}'])
    profiles = command(['minikube', 'profile', 'list', '-o', 'json'])
    profile = next(p for p in profiles['valid'] if p['Name'] == observer.context)
    result = {'models': models, 'docker_limits': docker, 'minikube_profile': profile}
    (folder / 'runtime-context.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    config = profile['Config']
    if config['CPUs'] != 8 or config['Memory'] != 12288:
        raise ValueError('Minikube profile must retain 8 CPUs and 12288 MiB')
    return result



def finish_scheduled_window(collection, folder, metadata):
    from observe import utc_now
    first = next(e for e in read_jsonl(folder / 'request-events.jsonl') if e['event'] == 'started')
    end = timestamp(first['scenario_started_at_utc']) + metadata['duration_seconds']
    collection.wait(max(0, end - timestamp(utc_now())))
    metadata['scheduled_profile_finished_at_utc'] = utc_now()

"""Preparation and configuration rules for the agreed main series, using existing records."""

import json
import math
import re
import subprocess
import time

from records import pilot_identity, read_jsonl, timestamp


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
                              text=True, timeout=10,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout.strip()
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
                # A delayed point from the same container cannot add a fresh interval.
                if point[0] < old[0] and point[2:] == old[2:] and point[1] <= old[1]:
                    continue
                if point != old:
                    self.previous.pop(uid, None)
                    self.low_intervals[uid] = 0
                continue
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
        result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=15,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
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

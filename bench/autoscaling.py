"""Manage one preliminary HPA run and retain logs of changing Ollama pods."""

import copy
import json
import re
import subprocess
import time

from pilot_records import pilot_identity, timestamp
from observe import utc_now


def ready(pod):
    return not pod['metadata'].get('deletionTimestamp') and any(
        c['type'] == 'Ready' and c['status'] == 'True' for c in pod.get('status', {}).get('conditions', []))


def target_hpa(sample, deployment):
    targets = [h for h in sample['hpa']['items'] if h['spec']['scaleTargetRef'].get('kind') == 'Deployment'
               and h['spec']['scaleTargetRef'].get('name') == deployment]
    if len(targets) > 1:
        raise ValueError('multiple HPAs target this Deployment')
    return targets[0] if targets else None


def configuration(deployment):
    spec = copy.deepcopy(deployment['spec'])
    spec.pop('replicas', None)
    return spec


class State:
    """Validate dynamic state without treating scaling or absent counters as failures."""

    def __init__(self, deployment, container, baseline, image_id):
        self.deployment, self.container = deployment, container
        self.baseline, self.image_id = baseline, image_id
        self.identities = {}
        self.hpa_spec = None
        self.hpa_required = False

    def accept(self, sample):
        if any(e.get('category') != 'missing_resource' for e in sample['errors']):
            raise ValueError('cluster API or resource scrape failed')
        if any(sample.get(key) is None for key in ('pods', 'deployments', 'hpa')):
            raise ValueError('required cluster state is missing')
        target = next((d for d in sample['deployments']['items'] if d['metadata']['name'] == self.deployment), None)
        if target is None:
            raise ValueError('Deployment is missing during collection')
        if configuration(target) != self.baseline:
            raise ValueError('Deployment configuration changed during collection')
        if not 1 <= target['spec'].get('replicas', 1) <= 3:
            raise ValueError('Deployment desired replicas outside 1-3')
        hpa = target_hpa(sample, self.deployment)
        if self.hpa_required and hpa is None:
            raise ValueError('expected HPA is missing')
        if hpa:
            if self.hpa_spec is None or hpa['spec'] != self.hpa_spec:
                raise ValueError('unexpected HPA configuration')
        found = set()
        for pod in sample['pods']['items']:
            uid = pod['metadata']['uid']
            if uid in found:
                raise ValueError('duplicate pod UID')
            found.add(uid)
            labels = target['spec']['selector']['matchLabels']
            if any(pod['metadata'].get('labels', {}).get(k) != v for k, v in labels.items()):
                raise ValueError('foreign pod in selected workload')
            container = next((c for c in pod.get('status', {}).get('containerStatuses', [])
                              if c['name'] == self.container), None)
            if container is None:
                continue
            identity = (container.get('containerID'), container.get('restartCount', 0), container.get('imageID'))
            old = self.identities.get(uid)
            if old and (identity[1] != old[1] or (old[0] and identity[0] and old[0] != identity[0])):
                raise ValueError('container restart detected')
            if old is None and identity[1] != 0:
                # The initial copy may carry an earlier restart; seeded by Session.prepare().
                raise ValueError('new container has restarted')
            if identity[2] and identity[2] != self.image_id:
                raise ValueError('container image changed')
            if not old or identity[0]:
                self.identities[uid] = identity
        return sample


class Logs:
    """One continuous, file-backed kubectl stream per observed running container UID."""

    def __init__(self, observer, folder, container):
        self.observer, self.folder, self.container = observer, folder, container
        (folder / 'pod-logs').mkdir()
        self.records, self.handles = {}, {}

    def update(self, sample):
        pods = {p['metadata']['uid']: p for p in sample['pods']['items']}
        for uid, pod in pods.items():
            status = next((c for c in pod.get('status', {}).get('containerStatuses', [])
                           if c['name'] == self.container), {})
            if uid not in self.records and 'running' in status.get('state', {}):
                command = ['kubectl', '--context', self.observer.context, '-n', self.observer.namespace,
                           'logs', pod['metadata']['name'], '-c', self.container, '--follow=true', '--timestamps=true']
                output = (self.folder / 'pod-logs' / f'{uid}.log').open('xb')
                error = (self.folder / 'pod-logs' / f'{uid}.stderr.txt').open('xb')
                try:
                    process = subprocess.Popen(command, stdout=output, stderr=error,
                                               creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                except BaseException:
                    output.close()
                    error.close()
                    raise
                self.handles[uid] = (process, output, error)
                self.records[uid] = {'pod_name': pod['metadata']['name'], 'attached_at_utc': sample['time'],
                                     'command': command, 'deleted': False, 'exit_code': None, 'complete': True}
            if uid in self.records and pod['metadata'].get('deletionTimestamp'):
                self.records[uid]['deleted'] = True
        for uid, (process, _, _) in self.handles.items():
            record = self.records[uid]
            if uid not in pods:
                record['deleted'] = True
            code = process.poll()
            if code is not None:
                record['exit_code'] = code
                # A terminated container stream can end just before deletion is observed.
                terminated = bool(next((c for c in pods.get(uid, {}).get('status', {}).get('containerStatuses', [])
                                        if c['name'] == self.container), {}).get('state', {}).get('terminated'))
                if code != 0 or not (record['deleted'] or terminated):
                    record['complete'] = False
                    self.save()
                    raise RuntimeError(f'pod log stream ended unexpectedly: {uid}, exit {code}')
        self.save()

    def save(self):
        (self.folder / 'log-coverage.json').write_text(json.dumps(self.records, indent=2) + '\n', encoding='utf-8')

    def stop(self):
        errors = []
        for uid, (process, output, error) in self.handles.items():
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    self.records[uid]['stopped_by_collector'] = True
                self.records[uid]['exit_code'] = process.returncode
            except (OSError, subprocess.SubprocessError) as failure:
                self.records[uid]['complete'] = False
                self.records[uid]['shutdown_error'] = str(failure)
                errors.append(f'{uid}: {failure}')
                try:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
                except (OSError, subprocess.SubprocessError) as fallback:
                    errors.append(f'{uid} kill fallback: {fallback}')
            finally:
                output.close()
                error.close()
        self.save()
        if errors:
            raise RuntimeError('log shutdown failed: ' + '; '.join(errors))


class Session:
    """Bounded preparation, observer hooks and independent restoration diagnostics."""

    def __init__(self, observer, folder, deployment, container, service, manifest):
        self.observer, self.folder = observer, folder
        self.deployment, self.container, self.service, self.manifest = deployment, container, service, manifest
        self.state, self.logs = None, None
        self.mutated = False
        self.applied_at_utc = None

    def command(self, *args):
        return self.observer.read('-n', self.observer.namespace, *args)

    def prepare(self):
        from fixed_replicas import capture_route, check_route
        snapshot = {name: json.loads(self.command('get', name, '-o', 'json'))
                    for name in ('deployment', 'pods', 'service', 'hpa')}
        (self.folder / 'runtime-before.json').write_text(json.dumps(snapshot, indent=2) + '\n', encoding='utf-8')
        target = next(d for d in snapshot['deployment']['items'] if d['metadata']['name'] == self.deployment)
        conflicts = [h for h in snapshot['hpa']['items'] if h['spec']['scaleTargetRef'].get('name') == self.deployment
                     and h['metadata']['name'] != 'ollama']
        if conflicts:
            raise ValueError('another HPA already controls the workload')
        if (self.deployment, self.observer.namespace, self.container) != ('ollama', 'inference', 'ollama'):
            raise ValueError('the HPA manifest supports only inference/ollama')
        named = [h for h in snapshot['hpa']['items'] if h['metadata']['name'] == 'ollama']
        if any(h['spec']['scaleTargetRef'].get('kind') != 'Deployment' or
               h['spec']['scaleTargetRef'].get('name') != self.deployment for h in named):
            raise ValueError('HPA name belongs to another workload')
        if self.service != 'ollama' or self.observer.selector != 'app=ollama':
            raise ValueError('autoscaling requires the Ollama Service and app=ollama selector')
        self.mutated = True
        self.command('delete', 'hpa', 'ollama', '--ignore-not-found')
        self.command('scale', f'deployment/{self.deployment}', '--replicas=1')
        deadline = time.monotonic() + 180
        last_error = None
        while time.monotonic() < deadline:
            sample = self.observer.collect(5)
            try:
                identity = pilot_identity(sample, self.deployment, self.container)
                route = capture_route(self.observer, self.service)
                check_route(route, [identity], target)
                (self.folder / 'service-route.json').write_text(json.dumps(route, indent=2) + '\n', encoding='utf-8')
                target = next(d for d in sample['deployments']['items'] if d['metadata']['name'] == self.deployment)
                self.state = State(self.deployment, self.container, configuration(target), identity['image_id'])
                self.state.identities[identity['pod_uid']] = (identity['container_id'], identity['restart_count'], identity['image_id'])
                self.logs = Logs(self.observer, self.folder, self.container)
                return
            except ValueError as error:
                last_error = str(error)
            time.sleep(2)
        raise RuntimeError(f'one-copy reset did not finish within 180 seconds: {last_error}')

    def accept(self, sample):
        self.state.accept(sample)
        self.logs.update(sample)

    def enable(self, collection):
        # Collection holds this lock for the full sample so it cannot race the apply.
        with collection.lock:
            self.command('apply', '-f', str(self.manifest))
            actual = json.loads(self.command('get', 'hpa', 'ollama', '-o', 'json'))
            self.state.hpa_spec = actual['spec']
            self.state.hpa_required = True
            self.applied_at_utc = utc_now()
            (self.folder / 'hpa-applied.json').write_text(json.dumps(actual, indent=2) + '\n', encoding='utf-8')
        deadline = time.monotonic() + 300
        consecutive, previous = 0, None
        while time.monotonic() < deadline:
            collection.wait(collection.interval)
            sample = collection.last
            if sample['time'] == previous:
                continue
            previous = sample['time']
            if hpa_ready(sample, self.deployment):
                consecutive += 1
                if consecutive == 2:
                    return
            else:
                consecutive = 0
        raise RuntimeError('HPA did not reach two numeric, ScalingActive one-copy samples within 300 seconds')

    def restore(self):
        result = {'attempted': self.mutated, 'successful': False, 'errors': []}
        if self.mutated:
            try:
                self.command('delete', 'hpa', 'ollama', '--ignore-not-found')
                self.command('scale', f'deployment/{self.deployment}', '--replicas=1')
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    pods = json.loads(self.command('get', 'pods', '-l', self.observer.selector, '-o', 'json'))['items']
                    if len(pods) == 1 and ready(pods[0]):
                        result['successful'] = True
                        break
                    time.sleep(2)
                if not result['successful']:
                    result['errors'].append('one ready copy was not restored within 180 seconds')
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                result['errors'].append(str(error))
        (self.folder / 'recovery.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        return result


def hpa_ready(sample, deployment):
    hpa = target_hpa(sample, deployment)
    pods = sample['pods']['items']
    if not hpa or len(pods) != 1 or not ready(pods[0]):
        return False
    status = hpa.get('status', {})
    numeric = any(m.get('type') == 'Resource' and m.get('resource', {}).get('name') == 'cpu'
                  and isinstance(m['resource'].get('current', {}).get('averageUtilization'), (int, float))
                  for m in status.get('currentMetrics', []))
    return numeric and status.get('currentReplicas') == 1 and status.get('desiredReplicas') == 1 and any(
        c['type'] == 'ScalingActive' and c['status'] == 'True' for c in status.get('conditions', []))


def check_samples(samples, metadata):
    """Replay dynamic invariants; API failures are errors, absent counter values are coverage gaps."""
    state = State(metadata['deployment'], metadata['container'], configuration(metadata['deployment_snapshot']),
                  metadata['initial_identity']['image_id'])
    i = metadata['initial_identity']
    state.identities[i['pod_uid']] = (i['container_id'], i['restart_count'], i['image_id'])
    state.hpa_spec = metadata.get('hpa_spec')
    applied = metadata.get('hpa_applied_at_utc')
    errors, gaps = [], []
    for sample in samples:
        state.hpa_required = bool(applied and timestamp(sample['time']) > timestamp(applied))
        try:
            state.accept(sample)
        except (ValueError, KeyError, StopIteration) as error:
            errors.append(str(error))
        gaps.extend({'time': sample['time'], **e} for e in sample['errors'] if e.get('category') == 'missing_resource')
    return errors, gaps


def log_summary(folder, metadata, samples):
    coverage = json.loads((folder / 'log-coverage.json').read_text(encoding='utf-8'))
    expected = {p['metadata']['uid'] for s in samples for p in s['pods']['items']
                if any('running' in c.get('state', {}) for c in p.get('status', {}).get('containerStatuses', [])
                       if c['name'] == metadata['container'])}
    errors = []
    if expected != set(coverage):
        errors.append('log coverage does not match observed running pods')
    result = {}
    start = timestamp(metadata['load_process_started_at_utc'])
    for uid in expected:
        if uid not in coverage:
            continue
        if not coverage[uid]['complete']:
            errors.append(f'incomplete pod log: {uid}')
        path = folder / 'pod-logs' / f'{uid}.log'
        responses = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if not re.search(r'\bPOST\s+"/api/generate"', line):
                continue
            match = re.search(r'\[GIN\].*?\|\s*(\d{3})\s*\|', line)
            if match is None:
                errors.append(f'unrecognized generation log: {uid}')
                continue
            at = line.split(' ', 1)[0]
            if timestamp(at) >= start:
                responses.append({'at_utc': at, 'http_status': int(match[1])})
        result[uid] = {'pod_name': coverage[uid]['pod_name'], 'http_responses_after_load_start': len(responses),
                       'first_observed_http_response_at_utc': responses[0]['at_utc'] if responses else None,
                       'http_responses': responses}
    return {'complete': not errors, 'errors': errors, 'pods': result,
            'method': 'Native HTTP completion logs; no client-request attribution or semantic success claim'}

"""Run the authorized nine-cell peak-12 comparison using the existing benchmark."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / 'bench'))
from analyze import assessment, load_results, main as analyze, phase_results, primary_resources
from run_pilot import parse_arguments
from runtime import BOUNDARY_WARNING, run_command, service_url

ORDER = (
    ('fixed-1', 'autoscaling', 'fixed-3'),
    ('autoscaling', 'fixed-3', 'fixed-1'),
    ('fixed-3', 'fixed-1', 'autoscaling'),
)
CELLS = [
    {'order': (repeat - 1) * 3 + slot, 'repetition': repeat, 'mode': mode}
    for repeat, modes in enumerate(ORDER, 1) for slot, mode in enumerate(modes, 1)
]
VERSION = 'peak12-v1'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def arguments(mode, folder, url):
    return ['--pilot-preparation', '--mode', mode, '--profile', 'burst',
            '--low-rate', '2', '--rate', '12', '--slo-ms', '5000',
            '--idle-seconds', '60', '--observer-interval', '5',
            '--post-seconds', '300' if mode == 'autoscaling' else '10',
            '--base-url', url, '--run-dir', str(folder),
            '--activity-note', 'No game or competing project load was detected in the pre-launch host snapshot.']


def comparison_input(data):
    """Adapt the reconciled preliminary report without changing saved evidence."""
    metadata = {**data['metadata'], 'protocol_version': VERSION}
    check = data['check']
    if metadata['mode'] == 'fixed-3':
        distribution = check.get('distribution', {})
        pods = distribution.get('pods', {})
        expected = {pod['pod_uid'] for pod in metadata['initial_identity']}
        if len(expected) != 3 or set(pods) != expected or any(p['completed'] <= 0 for p in pods.values()):
            raise ValueError('Expected measured Service traffic on each of the three initial pods')
        check = {**check, 'distribution': {**distribution, 'all_pods_active': True}}
    return {**data, 'metadata': metadata, 'check': check}


def require_assessable(assessed):
    problems = []
    if not assessed['data_valid']:
        problems.append('invalid data')
    if not assessed['duration_complete']:
        problems.append('scheduled load or post-load phase was incomplete')
    for key in ('unfinished', 'dropped'):
        if assessed[key] != 0:
            problems.append(f'{key}={assessed[key]} (expected 0)')
    if assessed['overall'] not in ('pass', 'fail'):
        problems.append(f"verdict={assessed['overall']}")
    if problems:
        raise ValueError('; '.join(problems + assessed['limitations']))


def review(folder, cell, exit_code, common, source_versions=None):
    data = load_results(folder)
    meta, check = data['metadata'], data['check']
    if (meta['exit_code'] != exit_code or meta['collector_exit_code'] != 0
            or meta['errors'] or not meta['collection_valid'] or not check['valid']):
        reasons = list(dict.fromkeys(meta['errors'] + check['errors']))
        details = '; '.join(reasons) or f"launcher={meta['exit_code']}, collector={meta['collector_exit_code']}"
        raise ValueError(f'Preparation or collection is incomplete: {details}')
    if check != read(folder / 'collection-check.json'):
        raise ValueError('Saved collection check differs from replay')
    warnings = (set(check['warnings']) | set(meta['warnings'])) - {BOUNDARY_WARNING}
    if warnings:
        raise ValueError(f'Unexpected warnings: {sorted(warnings)}')
    if (meta.get('protocol_version') is not None or meta['mode'] != cell['mode']
            or meta['profile'] != 'burst' or meta['rate'] != 12 or meta['low_rate'] != 2
            or meta['duration_seconds'] != 782):
        raise ValueError('Unexpected run settings')
    if cell['mode'] == 'autoscaling' and not meta.get('recovery', {}).get('successful'):
        raise ValueError('HPA recovery was not confirmed')
    for name, expected in meta['source_sha256'].items():
        archived = hashlib.sha256((folder / 'inputs' / name).read_bytes()).hexdigest()
        source = ROOT / ('deploy' if name.endswith('.yaml') else 'bench') / name
        current = hashlib.sha256(source.read_bytes()).hexdigest()
        allowed = (source_versions or {}).get(name)
        if archived != expected or (current != expected and not (allowed and {current, expected} <= set(allowed))):
            raise ValueError(f'Archived executable input mismatch: {name}')
        previous = common['hashes'].setdefault(name, expected)
        if previous != expected and not (allowed and {previous, expected} <= set(allowed)):
            raise ValueError(f'Executable input changed during the series: {name}')
    identity = meta['initial_identity']
    images = sorted({item['image_id'] for item in (identity if isinstance(identity, list) else [identity])})
    runtime = meta['runtime_context']
    environment = {'images': images, 'models': sorted({m['digest'] for m in runtime['models'].values()}),
                   'docker': runtime['docker_limits'],
                   'minikube': {key: runtime['minikube_profile']['Config'][key]
                                for key in ('CPUs', 'Memory', 'Driver')}}
    if len(images) != 1 or common.setdefault('environment', environment) != environment:
        raise ValueError('Image, model or runtime settings differ between runs')
    assessed = assessment(comparison_input(data))
    require_assessable(assessed)
    return assessed, phase_results(data), primary_resources(data)


from run_lock import exclusive_main


@exclusive_main
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series-dir', type=Path, required=True)
    parser.add_argument('--host-snapshot', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    series = args.series_dir.resolve()
    for cell in CELLS:
        mode = cell['mode']
        options = arguments(mode, series / 'dry-run-only', 'http://127.0.0.1:1')
        options, _, duration, prepared = parse_arguments(options)
        if not prepared or duration != 782 or options.mode != mode:
            raise ValueError('Fixed comparison preflight failed')
    if args.dry_run:
        print(json.dumps(CELLS, indent=2))
        return 0
    if args.host_snapshot is None:
        parser.error('--host-snapshot is required for a live series')
    series.mkdir(exist_ok=False)
    shutil.copyfile(__file__, series / 'driver.py')
    shutil.copyfile(args.host_snapshot, series / 'host-before.json')
    manifest = {'protocol': VERSION, 'status': 'starting', 'started_at_utc': utc_now(),
                'cells': CELLS, 'completed_runs': [], 'current_run': None}
    state = series / 'manifest.json'
    save(state, manifest)
    common = {'hashes': {}}
    try:
        with service_url(None) as url:
            kube = ['kubectl', '--context', 'ai-lab']
            subprocess.run([*kube, 'wait', '--for=condition=Ready', 'node', '--all', '--timeout=120s'], check=True)
            subprocess.run([*kube, '-n', 'inference', 'rollout', 'status', 'deployment/ollama', '--timeout=180s'], check=True)
            subprocess.run([*kube, '-n', 'kube-system', 'rollout', 'status', 'deployment/metrics-server', '--timeout=180s'], check=True)
            subprocess.run([*kube, 'top', 'nodes'], check=True)
            folders = []
            for cell in CELLS:
                folder = series / f"attempt-{cell['order']:02d}-{cell['mode']}-burst"
                output = series / f"attempt-{cell['order']:02d}-analysis"
                manifest.update(status='running', current_run=folder.name)
                save(state, manifest)
                print(f"Starting {cell['order']}/9: {folder.name}", flush=True)
                command = [sys.executable, '-B', str(ROOT / 'bench/run_pilot.py'),
                           *arguments(cell['mode'], folder, url)]
                code = run_command(command, folder)
                if code not in (0, 99):
                    launcher = read(folder / 'metadata.json') if (folder / 'metadata.json').is_file() else {}
                    detail = '; '.join(launcher.get('errors', []))
                    raise ValueError(f'launcher exit {code}' + (f': {detail}' if detail else ''))
                result, phases, resources = review(folder, cell, code, common)
                if analyze([str(folder), '--output-dir', str(output), '--no-plots']):
                    raise ValueError(f'{folder.name}: analysis failed')
                save(output / 'comparison-assessment.json', result)
                save(output / 'phase-results.json', phases)
                save(output / 'scheduled-resources.json', resources)
                folders.append(folder)
                manifest['completed_runs'].append({**cell, 'run': folder.name, 'analysis': output.name,
                                                   'verdict': result['overall'], 'peak': result['primary']})
                save(state, manifest)
                print(f"Saved {folder.name}: {result['overall']}", flush=True)
            if analyze([*(str(f) for f in folders), '--output-dir', str(series / 'combined-analysis'), '--no-plots']):
                raise ValueError('Combined analysis failed')
        manifest.update(status='complete', current_run=None, environment=common['environment'])
        return 0
    except KeyboardInterrupt:
        manifest.update(status='interrupted', error='Stopped before the next attempt.')
        return 130
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        attempt = manifest['current_run']
        reason = f'{attempt}: {error}' if attempt else str(error)
        manifest.update(status='failed', error=reason)
        print(f'Series stopped: {reason}', file=sys.stderr, flush=True)
        return 1
    finally:
        manifest['finished_at_utc'] = utc_now()
        save(state, manifest)


if __name__ == '__main__':
    raise SystemExit(main())

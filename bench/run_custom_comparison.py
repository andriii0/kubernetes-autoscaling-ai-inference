"""Six fixed CPU/request HPA cells, with explicit verified continuation after a stop."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from analyze import load_results, main as analyze, primary_resources
from analyze_custom_comparison import outcomes, summarize
from custom_metric_run import configuration, replay
from autoscaling import configuration as deployment_configuration
from records import pilot_identity
from custom_metrics import infrastructure_identity
from custom_metric_stack import render
from observe import Observer
from prepare_custom_metric import (ROOT, arguments as prep_arguments, assess_preparation, gateway_url,
                                   now, qualify, review, save, select)
from run_pilot import parse_arguments
from runtime import host_snapshot, run_command

CELLS = [{'order': i + 1, 'pair': i // 2 + 1, 'policy': policy}
         for i, policy in enumerate(('cpu', 'active-1', 'active-1', 'cpu', 'cpu', 'active-1'))]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arguments(folder, policy, url):
    args = prep_arguments(folder, 1, url)
    args[args.index('--custom-metric-policy') + 1] = policy
    args[args.index('--activity-note') + 1] = 'Six-cell CPU/request comparison through the same gateway; host snapshot archived.'
    return [*args, '--custom-metric-comparison']


def preparation_evidence(folder):
    manifest = read(folder / 'manifest.json')
    if manifest.get('status') != 'finished' or manifest.get('selected_target') != 1:
        raise ValueError('completed preparation with selected target 1 is required')
    results = []
    for target in (1, 2):
        run = folder / f'target-{target}'
        data = load_results(run)
        meta = data['metadata']
        if (not data['check']['valid'] or not meta['collection_valid'] or meta['errors']
                or not meta['recovery']['successful'] or not meta['recovery']['gateway_zero']['successful']):
            raise ValueError('preparation collection or cleanup is invalid')
        if data['check'] != read(run / 'collection-check.json'):
            raise ValueError('preparation collection replay changed')
        for name, expected in meta['source_sha256'].items():
            if Path(name).name != name or digest(run / 'inputs' / name) != expected:
                raise ValueError('preparation archive mismatch')
        for name, expected in meta['custom_bundle']['sha256'].items():
            if Path(name).name != name or digest(run / 'inputs/custom-stack' / name) != expected:
                raise ValueError('preparation config archive mismatch')
        assessed = assess_preparation(data)
        if not assessed['duration_complete'] or any(assessed[k] != 0 for k in ('dropped', 'unfinished')):
            raise ValueError('preparation workload incomplete')
        results.append({'target': target, 'qualification': qualify(data), 'metric': replay(run, data)})
    if select(results) != 1:
        raise ValueError('preparation selection replay differs')
    return {'manifest_sha256': digest(folder / 'manifest.json'), 'runs': results}


def source_hashes():
    return {p.name: digest(p) for p in (ROOT / 'bench').iterdir() if p.suffix in ('.py', '.js', '.json')}


def source_boundary(prepared, current, fix_record=None):
    changes = {name: {'prepared': old, 'comparison': current[name]}
               for name, old in prepared.items() if old != current[name]}
    collector = {name: values for name, values in changes.items()
                 if name in ('custom_metrics.py', 'custom_metric_run.py')}
    if set(changes) - {'run_pilot.py', 'prepare_custom_metric.py', *collector}:
        raise ValueError('unreviewed workload/collector change since preparation')
    if collector:
        if (not fix_record or fix_record.get('status') != 'verified'
                or fix_record.get('clock_contract') != 'bounded-clock-v2'
                or fix_record.get('changes') != collector):
            raise ValueError('collector change requires the exact verified clock-fix record')
    return {'changes': changes,
            'reason': 'Comparison v2 records the bounded clock correction; workload, routing and HPA policies are unchanged.'}


def recovered_identity(prep, recovery):
    """Allow only explicitly recorded instance renewal with the prepared images."""
    original = read(prep / 'target-2/custom-preflight.json')['identity']
    current = recovery.get('identity', {})
    if (recovery.get('previous_identity') != original or set(current) != set(original)
            or not isinstance(recovery.get('reason'), str) or not recovery['reason'].strip()):
        raise ValueError('invalid infrastructure recovery record')
    for name, identity in current.items():
        if (not isinstance(identity, dict) or set(identity) != set(original[name])
                or any(not isinstance(value, str) or not value for value in identity.values())
                or identity['image_id'] != original[name]['image_id']):
            raise ValueError('recovered infrastructure image or identity differs')
    return current


def live_preflight(observer, prep, bundle, expected_host, recovered=None):
    host = host_snapshot()
    if expected_host and any(host[k] != expected_host[k] for k in ('minikube_container', 'power_scheme_guid')):
        raise ValueError('host resource limits or power scheme changed')
    if host['minikube_container']['NanoCpus'] != 8000000000 or host['minikube_container']['Memory'] != 12884901888:
        raise ValueError('expected the prepared 8 CPU / 12 GiB node container')
    objects = json.loads(observer.read('get', '-f', str(bundle / 'stack.json'), '-o', 'json'))
    expected = read(prep / 'target-2/custom-installed-after.json')
    if configuration(objects) != configuration(expected):
        raise ValueError('installed stack differs from completed preparation')
    pods = json.loads(observer.read('-n', 'inference', 'get', 'pods', '-l', 'experiment=custom-metric-hpa', '-o', 'json'))
    expected_identity = (recovered_identity(prep, recovered) if recovered is not None
                         else read(prep / 'target-2/custom-preflight.json')['identity'])
    if infrastructure_identity(pods) != expected_identity:
        raise ValueError('metrics infrastructure changed since preparation')
    if json.loads(observer.read('-n', 'inference', 'get', 'hpa', '-o', 'json'))['items']:
        raise ValueError('an HPA is already installed')
    sample = observer.collect(5)
    identity = pilot_identity(sample, 'ollama', 'ollama')
    prepared = read(prep / 'target-2/metadata.json')
    deployment = next(d for d in sample['deployments']['items'] if d['metadata']['name'] == 'ollama')
    if (identity['image_id'] != prepared['initial_identity']['image_id'] or
            deployment_configuration(deployment) != deployment_configuration(prepared['deployment_snapshot'])):
        raise ValueError('backend image or configuration differs from preparation')
    model = json.loads(observer.read('get', '--raw', '/api/v1/namespaces/inference/services/ollama:11434/proxy/api/tags'))
    if prepared.get('latency_clock') == 'monotonic-v1':
        from build_k6 import runtime
        if runtime()[1] != prepared.get('timing_runtime'):
            raise ValueError('monotonic timing runtime differs from preparation')
    expected_models = read(prep / 'frozen-inputs.json')['models']
    actual_models = sorted({m['digest'] for m in model['models'] if m.get('name') == 'qwen2.5:0.5b'})
    if actual_models != expected_models:
        raise ValueError('model digest differs from preparation')
    return {'host': host, 'infrastructure': infrastructure_identity(pods), 'model_digests': actual_models,
            'installed': objects, 'backend': sample}


def resume_state(folder):
    """Replay a stopped prefix without writing or trusting saved performance verdicts."""
    manifest = read(folder / 'manifest.json')
    if (manifest.get('status') != 'stopped' or manifest.get('protocol') not in ('active-requests-comparison-v2', 'active-requests-comparison-v3')
            or manifest.get('selected_target') != 1 or manifest.get('cells') != CELLS
            or not 0 < len(manifest.get('completed', [])) < len(CELLS)):
        raise ValueError('resume requires a stopped v2 comparison with an accepted prefix')
    archived = read(folder / 'source-sha256.json')
    current = source_hashes()
    if set(archived) != set(current):
        raise ValueError('executable source set changed')
    for name, expected in archived.items():
        if Path(name).name != name or digest(folder / 'inputs' / name) != expected:
            raise ValueError('original source archive changed')
    changes = {name: {'original': old, 'continued': current[name]}
               for name, old in archived.items() if current[name] != old}
    if set(changes) - {'run_custom_comparison.py', 'prepare_custom_metric.py'}:
        raise ValueError('workload or collector changed; continuation is refused')
    references = [(archived, folder / 'inputs')]
    for continuation in manifest.get('continuations', []):
        name = continuation.get('record')
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError('invalid continuation record')
        record = folder / name
        boundary = read(record / 'source-boundary.json')['changes']
        if set(boundary) - {'run_custom_comparison.py', 'prepare_custom_metric.py'}:
            raise ValueError('invalid continuation source boundary')
        versions = dict(archived)
        for source, values in boundary.items():
            if values['original'] != archived[source]:
                raise ValueError('continuation source origin changed')
            versions[source] = values['continued']
        for source, expected in versions.items():
            if digest(record / 'inputs' / source) != expected:
                raise ValueError('continuation archive changed')
        references.append((versions, record / 'inputs'))
    seen = set()
    for cell, saved in zip(CELLS, manifest['completed']):
        if any(saved.get(key) != value for key, value in cell.items()):
            raise ValueError('completed cells are not the original consecutive prefix')
        for key in ('run', 'analysis'):
            if not isinstance(saved.get(key), str) or Path(saved[key]).name != saved[key]:
                raise ValueError('invalid saved result path')
            if saved[key] in seen:
                raise ValueError('a saved result is reused by another cell')
            seen.add(saved[key])
        run = folder / saved['run']
        meta = read(run / 'metadata.json')
        if (meta.get('custom_metric_policy') != cell['policy']
                or meta.get('duration_seconds') != 782 or meta.get('rate') != 12
                or meta.get('low_rate') != 2 or meta.get('post_seconds') != 300
                or meta.get('mode') != 'autoscaling' or meta.get('profile') != 'burst'):
            raise ValueError('accepted run settings or archived versions changed')
        source_dir = next((directory for versions, directory in references
                           if all(versions.get(name) == value for name, value in meta['source_sha256'].items())), None)
        if source_dir is None:
            raise ValueError('accepted run has an unrecorded source version')
        result = review(run, meta['exit_code'], comparison=True, source_dir=source_dir)
        data = load_results(run)
        result.update(outcomes=outcomes(data, run, cell['policy']), resources=primary_resources(data))
        # Compare the same JSON representation that was archived (tuples become lists).
        result = json.loads(json.dumps(result, allow_nan=False))
        if saved != {**cell, 'run': saved['run'], 'analysis': saved['analysis'], **result}:
            raise ValueError('accepted result differs from replay')
        if read(folder / saved['analysis'] / 'comparison.json') != result:
            raise ValueError('saved analysis differs from replay')
    failed = manifest.get('current')
    if not isinstance(failed, str) or Path(failed).name != failed:
        raise ValueError('stopped attempt is missing')
    pending = CELLS[len(manifest['completed']):]
    # Preflight can fail after a cell was accepted and before the next folder exists.
    # The accepted prefix above has already been fully replayed. Never repeat its load.
    if failed == manifest['completed'][-1]['run']:
        return manifest, current, pending, changes
    expected = f"attempt-{pending[0]['order']:02d}-{pending[0]['policy']}"
    if failed != expected and not failed.startswith(expected + '-retry-'):
        raise ValueError('stopped attempt does not match the next cell')
    meta = read(folder / failed / 'metadata.json')
    if meta.get('exit_code') in (0, 99) or meta.get('collection_valid') is not False:
        raise ValueError('stopped attempt needs assessment, not replacement load')
    return manifest, current, pending, changes


def next_paths(folder, cell):
    name = f"attempt-{cell['order']:02d}-{cell['policy']}"
    run = folder / name
    retry = 0
    while run.exists():
        retry += 1
        run = folder / f'{name}-retry-{retry:02d}'
    analysis = folder / (f'{run.name}-analysis' if retry else f"attempt-{cell['order']:02d}-analysis")
    if analysis.exists():
        raise ValueError('analysis destination already exists')
    return run, analysis


from run_lock import exclusive_main


@exclusive_main
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--preparation-dir', type=Path, required=True)
    parser.add_argument('--collector-fix-record', type=Path)
    parser.add_argument('--resume', action='store_true', help='Replay an existing stopped prefix and run only its remaining cells')
    parser.add_argument('--recovered-infrastructure-record', type=Path,
                        help='Explicit instance-renewal record, only when resuming between complete pairs')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    folder, prep = args.output_dir.resolve(), args.preparation_dir.resolve()
    for cell in CELLS:
        parse_arguments(arguments(folder / 'unused', cell['policy'], 'http://127.0.0.1:1'))
    evidence = preparation_evidence(prep)
    state = resume_state(folder) if args.resume else None
    if state and Path(state[0]['preparation_dir']).resolve() != prep:
        raise ValueError('resume preparation directory differs from the original comparison')
    saved_recovery = None
    if state:
        for continuation in reversed(state[0].get('continuations', [])):
            path = folder / continuation['record'] / 'infrastructure-recovery.json'
            if path.is_file():
                saved_recovery = read(path)
                break
    recovered = read(args.recovered_infrastructure_record) if args.recovered_infrastructure_record else saved_recovery
    if recovered is not None:
        if not state or (len(state[0]['completed']) % 2 and recovered != saved_recovery):
            raise ValueError('infrastructure renewal requires a stopped comparison between complete pairs')
        recovered_identity(prep, recovered)
    if not args.execute:
        print(json.dumps({'cells': state[2] if state else CELLS, 'preparation': evidence,
                          'accepted': len(state[0]['completed']) if state else 0,
                          'source_changes': state[3] if state else {}, 'recovered_infrastructure': recovered, 'runtime_changed': False}, indent=2))
        return 0
    lock = None
    if state:
        lock = folder / 'resume.lock'
        with lock.open('x', encoding='utf-8') as handle:
            handle.write(str(os.getpid()))
        manifest, frozen, pending, changes = state
        record = folder / f'resume-{os.getpid()}'
        try:
            record.mkdir(exist_ok=False)
            (record / 'manifest-before.json').write_bytes((folder / 'manifest.json').read_bytes())
            save(record / 'source-boundary.json', {'changes': changes,
                 'reason': 'Explicit continuation and archived-prefix review only; workload and collectors are unchanged.'})
            (record / 'inputs').mkdir()
            for name in frozen:
                shutil.copyfile(ROOT / 'bench' / name, record / 'inputs' / name)
        except BaseException:
            lock.unlink()
            raise
        manifest.setdefault('continuations', []).append({'record': record.name, 'started_at': now(),
                     'replaces': manifest['current'], 'previous_errors': manifest['errors']})
        manifest.update(status='starting', pid=os.getpid(), resumed_at=now(), finished_at=None, errors=[])
    else:
        folder.mkdir(parents=True, exist_ok=False)
        record, pending = folder, CELLS
        manifest = {'status': 'starting', 'protocol': 'active-requests-comparison-v3', 'pid': os.getpid(),
                    'started_at': now(), 'preparation_dir': str(prep), 'selected_target': 1,
                    'cells': CELLS, 'completed': [], 'current': None, 'errors': []}
        frozen = None
    try:
        save(folder / 'manifest.json', manifest)
        save(record / 'preparation-check.json', evidence)
        if recovered is not None:
            save(record / 'infrastructure-recovery.json', recovered)
        if not state:
            render(folder / 'bundle')
            frozen = source_hashes()
            save(folder / 'source-sha256.json', frozen)
            # Keep a full executable archive before the first run, without copying results or secrets.
            (folder / 'inputs').mkdir()
            for name in frozen:
                shutil.copyfile(ROOT / 'bench' / name, folder / 'inputs' / name)
            prep_sources = read(prep / 'target-2/metadata.json')['source_sha256']
            fix_record = read(args.collector_fix_record) if args.collector_fix_record else None
            save(folder / 'preparation-code-boundary.json', source_boundary(prep_sources, frozen, fix_record))
            if fix_record:
                save(folder / 'collector-fix.json', fix_record)
        observer = Observer()
        expected_host = read(folder / 'preflight.json')['host'] if state else None
        baseline = live_preflight(observer, prep, folder / 'bundle', expected_host, recovered)
        save(record / 'preflight.json', baseline)
        with gateway_url(record) as url:
            for cell in pending:
                if source_hashes() != frozen:
                    raise ValueError('executable inputs changed during comparison')
                preflight = live_preflight(observer, prep, folder / 'bundle', baseline['host'], recovered)
                save(record / f"preflight-{cell['order']:02d}.json", preflight)
                run, output = next_paths(folder, cell)
                manifest.update(status='running', current=run.name)
                save(folder / 'manifest.json', manifest)
                code = run_command([sys.executable, '-B', str(ROOT / 'bench/run_pilot.py'),
                                    *arguments(run, cell['policy'], url)], run)
                result = review(run, code, comparison=True)
                meta = read(run / 'metadata.json')
                if (meta['custom_metric_policy'] != cell['policy'] or meta['duration_seconds'] != 782
                        or meta['rate'] != 12 or meta['low_rate'] != 2 or meta['post_seconds'] != 300):
                    raise ValueError('comparison settings mismatch')
                if meta['initial_identity']['image_id'] != read(prep / 'target-2/metadata.json')['initial_identity']['image_id']:
                    raise ValueError('backend image changed since preparation')
                data = load_results(run)
                result.update(outcomes=outcomes(data, run, cell['policy']), resources=primary_resources(data))
                if analyze([str(run), '--output-dir', str(output)]):
                    raise ValueError('offline analysis failed')
                save(output / 'comparison.json', result)
                manifest['completed'].append({**cell, 'run': run.name, 'analysis': output.name, **result})
                save(folder / 'manifest.json', manifest)
        save(folder / 'comparison-summary.json', summarize(manifest['completed']))
        manifest.update(status='finished', current=None)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        manifest.update(status='stopped', errors=[str(error)])
        print(f'Comparison stopped: {error}', flush=True)
        return 1
    finally:
        manifest['finished_at'] = now()
        save(folder / 'manifest.json', manifest)
        if lock:
            lock.unlink()


if __name__ == '__main__':
    raise SystemExit(main())

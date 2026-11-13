"""Six fixed CPU/request HPA cells. Stops on invalid evidence; never replaces runs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
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


def live_preflight(observer, prep, bundle, expected_host):
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
    if infrastructure_identity(pods) != read(prep / 'target-2/custom-preflight.json')['identity']:
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
    expected_models = read(prep / 'frozen-inputs.json')['models']
    actual_models = sorted({m['digest'] for m in model['models'] if m.get('name') == 'qwen2.5:0.5b'})
    if actual_models != expected_models:
        raise ValueError('model digest differs from preparation')
    return {'host': host, 'infrastructure': infrastructure_identity(pods), 'model_digests': actual_models,
            'installed': objects, 'backend': sample}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--preparation-dir', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    folder, prep = args.output_dir.resolve(), args.preparation_dir.resolve()
    for cell in CELLS:
        parse_arguments(arguments(folder / 'unused', cell['policy'], 'http://127.0.0.1:1'))
    evidence = preparation_evidence(prep)
    if not args.execute:
        print(json.dumps({'cells': CELLS, 'preparation': evidence, 'runtime_changed': False}, indent=2))
        return 0
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {'status': 'starting', 'protocol': 'active-requests-comparison-v1', 'pid': os.getpid(),
                'started_at': now(), 'preparation_dir': str(prep), 'selected_target': 1,
                'cells': CELLS, 'completed': [], 'current': None, 'errors': []}
    save(folder / 'manifest.json', manifest)
    try:
        save(folder / 'preparation-check.json', evidence)
        render(folder / 'bundle')
        frozen = source_hashes()
        save(folder / 'source-sha256.json', frozen)
        # Keep a full executable archive before the first run, without copying results or secrets.
        (folder / 'inputs').mkdir()
        for name in frozen:
            shutil.copyfile(ROOT / 'bench' / name, folder / 'inputs' / name)
        prep_sources = read(prep / 'target-2/metadata.json')['source_sha256']
        changes = {name: {'prepared': old, 'comparison': frozen[name]}
                   for name, old in prep_sources.items() if old != frozen[name]}
        if set(changes) - {'run_pilot.py', 'prepare_custom_metric.py'}:
            raise ValueError('unreviewed workload/collector change since preparation')
        save(folder / 'preparation-code-boundary.json', {
            'changes': changes, 'reason': 'Explicit comparison metadata/archive and shared review branch only; workload and collector unchanged.'})
        observer = Observer()
        baseline = live_preflight(observer, prep, folder / 'bundle', None)
        save(folder / 'preflight.json', baseline)
        with gateway_url(folder) as url:
            for cell in CELLS:
                if source_hashes() != frozen:
                    raise ValueError('executable inputs changed during comparison')
                preflight = live_preflight(observer, prep, folder / 'bundle', baseline['host'])
                save(folder / f"preflight-{cell['order']:02d}.json", preflight)
                run = folder / f"attempt-{cell['order']:02d}-{cell['policy']}"
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
                output = folder / f"attempt-{cell['order']:02d}-analysis"
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


if __name__ == '__main__':
    raise SystemExit(main())

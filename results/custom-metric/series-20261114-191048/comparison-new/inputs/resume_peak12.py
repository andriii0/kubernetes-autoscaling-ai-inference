"""Replay and continue the saved peak-12 driver without editing measured inputs."""

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

from runtime import host_snapshot
from run_peak12_comparison import comparison_input, require_assessable, review
from main_protocol import runtime_context
from observe import Observer


def comparison_assessment(data, assess):
    result = assess(comparison_input(data))
    require_assessable(result)
    return result


def load_driver(series):
    spec = importlib.util.spec_from_file_location('saved_peak12_driver', series / 'driver.py')
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    assess = driver.assessment
    driver.assessment = lambda data: comparison_assessment(data, assess)
    repair = series / 'log-recovery.json'
    if repair.exists():
        versions = driver.read(repair)['source_versions']
        driver.review = lambda folder, cell, code, common: review(folder, cell, code, common, versions)
    return driver


def replay(driver, series):
    manifest = driver.read(series / 'manifest.json')
    if manifest['protocol'] != driver.VERSION or manifest['cells'] != driver.CELLS:
        raise ValueError('Series protocol or order differs from saved driver')
    common, saved, pending = {'hashes': {}}, [], []
    recovery = driver.read(series / 'log-recovery.json') if (series / 'log-recovery.json').exists() else {}
    for cell in driver.CELLS:
        folder = series / f"attempt-{cell['order']:02d}-{cell['mode']}-burst"
        folder = series / recovery.get('runs', {}).get(folder.name, folder.name)
        if not folder.exists():
            pending.append(cell)
            continue
        if pending:
            raise ValueError('Saved attempts are not a consecutive prefix')
        meta = driver.read(folder / 'metadata.json')
        if meta.get('exit_code') not in (0, 99):
            raise ValueError(f'Partial or failed attempt preserved: {folder.name}')
        result = driver.review(folder, cell, meta['exit_code'], common)
        saved.append((cell, folder, result))
    return manifest, common, saved, pending


def record(driver, series, cell, folder, reviewed, manifest):
    result, phases, resources = reviewed
    output = series / f"attempt-{cell['order']:02d}-analysis"
    if not output.exists():
        if driver.analyze([str(folder), '--output-dir', str(output), '--no-plots']):
            raise ValueError(f'Analysis failed: {folder.name}')
        driver.save(output / 'comparison-assessment.json', result)
        driver.save(output / 'phase-results.json', phases)
        driver.save(output / 'scheduled-resources.json', resources)
    else:
        if driver.read(output / 'comparison-assessment.json') != result:
            raise ValueError(f'Existing assessment differs: {output.name}')
    manifest['completed_runs'].append({**cell, 'run': folder.name, 'analysis': output.name,
                                       'verdict': result['overall'], 'peak': result['primary']})


from run_lock import exclusive_main


@exclusive_main
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series-dir', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    series = args.series_dir.resolve()
    driver = load_driver(series)
    manifest, common, saved, pending = replay(driver, series)
    for cell, folder, reviewed in saved:
        print(f"Replayed {cell['order']}/9: {folder.name}: {reviewed[0]['overall']}", flush=True)
    print('Pending: ' + ', '.join(str(c['order']) for c in pending), flush=True)
    if args.dry_run or not pending:
        return 0
    host = host_snapshot()
    stamp = driver.utc_now().replace(':', '').replace('.', '-')
    recovery = series / ('resume-' + stamp)
    recovery.mkdir()
    shutil.copyfile(series / 'manifest.json', recovery / 'manifest-before.json')
    shutil.copyfile(__file__, recovery / 'resume_peak12.py')
    shutil.copyfile(Path(__file__).with_name('run_peak12_comparison.py'), recovery / 'run_peak12_comparison.py')
    if (series / 'log-recovery.json').exists():
        shutil.copyfile(series / 'log-recovery.json', recovery / 'log-recovery.json')
        shutil.copyfile(Path(__file__).with_name('recover_peak12_logs.py'), recovery / 'recover_peak12_logs.py')
    driver.save(recovery / 'host-before.json', host)
    observer = Observer()
    pods = json.loads(observer.read('-n', observer.namespace, 'get', 'pods', '-o', 'json'))['items']
    pods = [pod for pod in pods if pod['metadata'].get('labels', {}).get('app') == 'ollama'
            and not pod['metadata'].get('deletionTimestamp')]
    if not pods:
        raise ValueError('No current inference pods for environment verification')
    runtime = runtime_context(observer, pods, recovery, 'qwen2.5:0.5b')
    environment = dict(images=sorted({s['imageID'] for pod in pods
                       for s in pod['status'].get('containerStatuses', []) if s['name'] == 'ollama'}),
                       models=sorted({m['digest'] for m in runtime['models'].values()}),
                       docker=runtime['docker_limits'],
                       minikube={key: runtime['minikube_profile']['Config'][key]
                                 for key in ('CPUs', 'Memory', 'Driver')})
    if environment != common['environment']:
        raise ValueError('Current image, model or runtime settings differ from saved prefix')
    driver.save(recovery / 'repair.json', dict(started_at_utc=driver.utc_now(),
        previous_finished_at_utc=manifest.get('finished_at_utc'),
        reason='Replay validated evidence and recorded log recovery/source boundary when present',
        replayed=[folder.name for _, folder, _ in saved]))
    manifest.update(status='resuming', completed_runs=[], current_run=None)
    manifest.pop('error', None)
    manifest.pop('finished_at_utc', None)
    manifest.setdefault('resumptions', []).append(recovery.name)
    state = series / 'manifest.json'
    try:
        for cell, folder, reviewed in saved:
            record(driver, series, cell, folder, reviewed, manifest)
        driver.save(state, manifest)
        with driver.service_url(None) as url:
            kube = ['kubectl', '--context', 'ai-lab']
            for command in ([*kube, 'wait', '--for=condition=Ready', 'node', '--all', '--timeout=120s'],
                            [*kube, '-n', 'inference', 'rollout', 'status', 'deployment/ollama', '--timeout=180s'],
                            [*kube, '-n', 'kube-system', 'rollout', 'status', 'deployment/metrics-server', '--timeout=180s'],
                            [*kube, 'top', 'nodes']):
                subprocess.run(command, check=True)
            for cell in pending:
                folder = series / f"attempt-{cell['order']:02d}-{cell['mode']}-burst"
                if folder.exists():
                    raise ValueError(f'Attempt already exists: {folder.name}')
                manifest.update(status='running', current_run=folder.name)
                driver.save(state, manifest)
                print(f"Starting {cell['order']}/9: {folder.name}", flush=True)
                code = driver.run_command([sys.executable, '-B', str(driver.ROOT / 'bench/run_pilot.py'),
                                           *driver.arguments(cell['mode'], folder, url)], folder)
                if code not in (0, 99):
                    raise ValueError(f'{folder.name}: launcher exit {code}; attempt preserved')
                record(driver, series, cell, folder, driver.review(folder, cell, code, common), manifest)
                driver.save(state, manifest)
        folders = [str(series / row['run']) for row in manifest['completed_runs']]
        if driver.analyze([*folders, '--output-dir', str(series / 'combined-analysis'), '--no-plots']):
            raise ValueError('Combined analysis failed')
        manifest.update(status='complete', current_run=None, environment=common['environment'])
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        manifest.update(status='failed', error=str(error))
        print(f'Series stopped: {error}', flush=True)
        return 1
    except KeyboardInterrupt:
        manifest.update(status='interrupted', error='Interrupted during continuation')
        return 130
    finally:
        manifest['finished_at_utc'] = driver.utc_now()
        driver.save(state, manifest)


if __name__ == '__main__':
    raise SystemExit(main())

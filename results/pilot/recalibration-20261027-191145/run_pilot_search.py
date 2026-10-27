"""Select fresh one-copy rates with bounded probes and four confirmations."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import analyze
from pilot_records import timestamp
from run_series import BOUNDARY_WARNING, run_command, service_url
from run_wait_pair import host_snapshot


ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = (8, 10, 12, 16, 20)


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def target_missed(p95_ms, failed, completed):
    if p95_ms is None or completed <= 0:
        raise ValueError('Cannot select a rate without successful latency and completed requests')
    return p95_ms > 5000 or failed / completed > .01


def confirmation_passes(rows):
    if [r['label'] for r in rows] != ['low-1', 'peak-1', 'low-2', 'peak-2']:
        return False
    return all(r['target_missed'] == r['label'].startswith('peak') for r in rows)


def inspect(folder, duration):
    data = analyze.load_results(folder)
    metadata, check = data['metadata'], data['check']
    if not check['valid'] or metadata['exit_code'] not in (0, 99) or metadata['errors']:
        raise ValueError(f'Invalid collection/preparation: {folder}')
    counts = check['counts']
    if counts['unfinished'] or counts['dropped']:
        raise ValueError('Incomplete delivery or completion; no next probe')
    warnings = set(check['warnings']) | set(metadata.get('warnings', []))
    if warnings - {BOUNDARY_WARNING}:
        raise ValueError(f'Warnings require review: {sorted(warnings)}')
    if metadata.get('purpose') != 'pilot-recalibration' or metadata.get('protocol_version'):
        raise ValueError('This search must remain outside the completed main protocol')
    end = timestamp(check['load_window']['scheduled_end_at_utc'])
    if (metadata['duration_seconds'] != duration or
            timestamp(metadata['scheduled_profile_finished_at_utc']) < end):
        raise ValueError('Scheduled probe duration is incomplete')
    metrics = analyze.calculate_metrics(data)
    row = dict(rate=metadata['rate'], duration_seconds=duration, **counts,
               p95_ms=metrics['p95_ms'], mean_ms=metrics['mean_ms'], warnings=sorted(warnings))
    row['target_missed'] = target_missed(row['p95_ms'], counts['failed'], counts['completed'])
    # Any response failure also stops further discovery, even below the 1% target.
    row['response_failure'] = counts['failed'] > 0
    context = metadata['runtime_context']
    controlled = dict(workload=metadata['workload'], initial_identity=metadata['initial_identity'],
                      source_sha256=metadata['source_sha256'],
                      model_digests=sorted(m['digest'] for m in context['models'].values()))
    return row, controlled


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    series = args.series_dir.resolve()
    series.mkdir(parents=True, exist_ok=False)
    manifest = dict(purpose='pilot-recalibration', status='preparing',
                    started_at_utc=datetime.now(timezone.utc).isoformat(),
                    search_rates_per_10s=list(CANDIDATES), low_candidate=2, low_fallback=1,
                    probe_seconds=120, confirmation_seconds=300,
                    confirmation_order=['low-1', 'peak-1', 'low-2', 'peak-2'],
                    criteria={'p95_ms': 5000, 'error_rate': .01, 'unfinished': 0, 'dropped': 0},
                    maximum_schedule_seconds=7200, completed_runs=[],
                    limitation='Current-host rate selection; not an HPA benefit or historical-cause test')
    shutil.copyfile(__file__, series / 'run_pilot_search.py')
    manifest['runner_sha256'] = hashlib.sha256((series / 'run_pilot_search.py').read_bytes()).hexdigest()
    save(series / 'manifest.json', manifest)
    deadline, controlled = time.monotonic() + 7200, None

    def finish(status, reason):
        manifest.update(status=status, reason=reason, finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(series / 'manifest.json', manifest)
        print(f'{status}: {reason}', flush=True)
        return 0 if status == 'finished' else 1

    def run(url, label, rate, seconds):
        nonlocal controlled
        if time.monotonic() >= deadline:
            raise ValueError('Two-hour scheduling budget reached; no further run')
        number = len(manifest['completed_runs']) + 1
        name = f'{number:02d}-{label}-rate-{rate}'
        folder = series / name
        host = host_snapshot()
        save(series / f'{name}-host-before.json', host)
        manifest.update(status='running', current_run=name, current_label=label,
                        current_rate=rate, current_duration_seconds=seconds)
        save(series / 'manifest.json', manifest)
        command = [sys.executable, '-B', str(ROOT / 'bench/run_pilot.py'), '--pilot-preparation',
                   '--mode', 'fixed-1', '--profile', 'steady', '--rate', str(rate), '--duration', f'{seconds}s',
                   '--slo-ms', '5000', '--base-url', url, '--run-dir', str(folder),
                   '--activity-note', 'No For Honor or other project generator found; pre-launch host snapshot saved.']
        print(f'Starting {name}: {seconds}s measured load', flush=True)
        code = run_command(command, folder)
        if code not in (0, 99):
            raise ValueError(f'Launcher exit {code}; no next run: {name}')
        row, current = inspect(folder, seconds)
        current['minikube_container'] = host['minikube_container']
        current['power_scheme_guid'] = host['power_scheme_guid']
        if controlled is not None and current != controlled:
            raise ValueError('Controlled input/runtime identity changed; retain evidence and stop')
        controlled = current
        if analyze.main([str(folder), '--output-dir', str(series / f'{name}-analysis'), '--no-plots']):
            raise ValueError(f'Analysis failed: {name}')
        row.update(label=label, run=name)
        manifest['completed_runs'].append(row)
        manifest['current_run'] = None
        save(series / 'manifest.json', manifest)
        print(f"Saved {name}: p95={row['p95_ms']:.1f} ms, failed={row['failed']}, target_missed={row['target_missed']}", flush=True)
        return row

    try:
        with service_url(None) as url:
            low = 2
            baseline = run(url, 'discovery-low', low, 120)
            if baseline['target_missed'] or baseline['response_failure']:
                low = 1
                baseline = run(url, 'discovery-low-fallback', low, 120)
            if baseline['target_missed'] or baseline['response_failure']:
                return finish('inconclusive', 'Neither predefined low candidate is calm')
            manifest['selected_low'] = low
            peak = None
            for rate in CANDIDATES:
                probe = run(url, 'discovery-peak', rate, 120)
                if probe['target_missed']:
                    peak = rate
                    break
                if probe['response_failure']:
                    return finish('inconclusive', 'Response failure before a target-miss candidate; no escalation')
            if peak is None:
                return finish('inconclusive', 'No target-miss peak in predefined candidates; no further load')
            manifest.update(selected_peak=peak, stage='confirmation')
            save(series / 'manifest.json', manifest)
            confirmations = []
            for label in manifest['confirmation_order']:
                confirmations.append(run(url, label, low if label.startswith('low') else peak, 300))
            manifest['selection_confirmed'] = confirmation_passes(confirmations)
            if not manifest['selection_confirmed']:
                return finish('inconclusive', 'Low/peak behavior was not repeated in both confirmations')
            return finish('finished', 'Low and peak confirmed twice; no HPA or additional matrix scheduled')
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        return finish('stopped', str(error))


if __name__ == '__main__':
    raise SystemExit(main())

"""Continue an existing v1.1 series with the existing launcher and analyzer."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from analyze import assessment, load_results
from main_protocol import matrix
from runtime import BOUNDARY_WARNING, run_command, service_url


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SERIES = ROOT / 'results/main/series-2026-10-25-v1.1'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def paths(series, row):
    number = row['planned_order']
    return (series / f"attempt-{number:02d}-{row['mode']}-{row['profile']}",
            series / f'attempt-{number:02d}-analysis')


def check_inputs(metadata):
    """Compare the measured executable inputs with today's files, without editing them."""
    for name, expected in metadata['source_sha256'].items():
        path = ROOT / ('deploy' if name.endswith('.yaml') else 'bench') / name
        if hashlib.sha256(path.read_bytes()).hexdigest().lower() != expected.lower():
            raise ValueError(f'Executable input changed: {path}')


def review(folder, row):
    data = load_results(folder)
    metadata, check = data['metadata'], data['check']
    expected = dict(row, actual_order=row['planned_order'], protocol_version='1.1')
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError(f'{folder.name}: matrix identity mismatch; review manually')
    if (metadata.get('exit_code') not in (0, 99) or metadata.get('collector_exit_code') != 0
            or metadata.get('errors') or not metadata.get('collection_valid')):
        raise ValueError(f'{folder.name}: preparation/collection did not finish normally')
    check_inputs(metadata)
    result = json.loads(json.dumps(assessment(data)))
    if result != read_json(folder / 'assessment.json'):
        raise ValueError(f'{folder.name}: saved assessment differs from replay')
    if (not result['data_valid'] or not result['duration_complete']
            or result['unfinished'] != 0 or result['dropped'] != 0
            or result['overall'] not in ('pass', 'fail')):
        raise ValueError(f'{folder.name}: incomplete or not-assessable evidence; review manually')
    warnings = set(check['warnings']) | set(metadata.get('warnings', []))
    if warnings - {BOUNDARY_WARNING}:
        raise ValueError(f'{folder.name}: warnings require review: {sorted(warnings)}')
    if warnings:
        print(f'{folder.name}: retained the existing 1-ms boundary warning.', flush=True)
    return result


def check_analysis(folder, output, result):
    required = ('analysis.json', 'summary.csv', 'assessments.json', 'primary-resources.json', 'README.md')
    if any(not (output / name).is_file() for name in required):
        raise ValueError(f'Incomplete analysis at {output}; preserve it and review manually')
    if read_json(output / 'assessments.json').get(folder.name) != result:
        raise ValueError(f'Analysis assessment differs at {output}')


def pending_rows(series):
    if not series.is_dir():
        raise ValueError('Use an existing main-series directory')
    rows = matrix()
    known = {paths(series, row)[0].name for row in rows}
    for entry in series.glob('attempt-*'):
        if not entry.is_dir() or entry.name.endswith('-analysis'):
            continue
        if entry.name not in known:
            raise ValueError(f'Unexpected attempt {entry.name}; replacements need manual review')
    pending, gap = [], False
    for row in rows:
        folder, output = paths(series, row)
        if folder.exists():
            if gap:
                raise ValueError('Saved attempts are not a consecutive prefix of the matrix')
            result = review(folder, row)
            check_analysis(folder, output, result)
            print(f"Keep {folder.name}: {result['overall']}", flush=True)
        else:
            if output.exists():
                raise ValueError(f'Analysis exists without its attempt: {output}')
            pending.append(row)
            gap = True
    if len(pending) == len(rows):
        raise ValueError('This continuation command needs at least one completed main attempt')
    return pending




def execute(series, rows, base_url, activity):
    config = read_json(ROOT / 'bench/workload.json')['main_protocol']
    for row in rows:
        folder, output = paths(series, row)
        if folder.exists() or output.exists():
            raise ValueError(f'Refusing an existing attempt or analysis path: {folder}')
        print(f"Starting {row['planned_order']}/18: {row['mode']} / {row['profile']}", flush=True)
        command = [sys.executable, '-B', str(ROOT / 'bench/run_pilot.py'),
                   '--protocol-version', config['version'], '--rate', str(config['peak_rate']),
                   '--base-url', base_url, '--activity-note', activity, '--run-dir', str(folder)]
        for key, value in dict(row, actual_order=row['planned_order']).items():
            command.extend(['--' + key.replace('_', '-'), str(value)])
        code = run_command(command, folder)
        if code not in (0, 99):
            raise ValueError(f'{folder.name}: launcher exit {code}; saved files retained, no next attempt')
        result = review(folder, row)
        code = run_command([sys.executable, '-B', str(ROOT / 'bench/analyze.py'), str(folder),
                            '--output-dir', str(output), '--no-plots'])
        if code != 0:
            raise ValueError(f'{folder.name}: analysis failed; no next attempt')
        check_analysis(folder, output, result)
        print(f"Saved {folder.name}: {result['overall']}; analysis: {output}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series-dir', type=Path, default=DEFAULT_SERIES)
    parser.add_argument('--base-url', help='Reuse an already open Service tunnel')
    parser.add_argument('--activity-note', help='Other heavy activity on this computer')
    parser.add_argument('--dry-run', action='store_true', help='Check saved records and list pending cells; no runtime changes')
    args = parser.parse_args(argv)
    try:
        series = args.series_dir.resolve()
        rows = pending_rows(series)
        print(f'{18 - len(rows)}/18 saved; {len(rows)} remaining.', flush=True)
        for row in rows:
            print(f"  {row['planned_order']}: {row['mode']} / {row['profile']} / repetition {row['repetition']}")
        if args.dry_run or not rows:
            return 0
        if not all(shutil.which(name) for name in ('git', 'minikube', 'k6')):
            raise ValueError('git, minikube and k6 must be available on PATH')
        activity = args.activity_note or input('Other heavy activity (close games first; describe it or enter none): ').strip()
        if not activity:
            raise ValueError('Record current activity before starting')
        with service_url(args.base_url) as url:
            execute(series, rows, url, activity)
        print('All 18 cells have saved valid/full-load records and analysis. Comparative findings still need review.')
        return 0
    except KeyboardInterrupt:
        print('Series stopped; no next attempt. Preserve the current folder and review it before resuming.', file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError, EOFError, subprocess.SubprocessError) as error:
        print(f'Series stopped: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

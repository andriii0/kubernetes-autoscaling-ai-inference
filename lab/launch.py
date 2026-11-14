"""Small pilot adapter; measurement and analysis stay in the existing scripts."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = dict(mode='fixed-1', profile='steady', rate=2, low_rate=2,
                duration_seconds=120, slo_ms=5000)


def pilot_settings(value=None):
    if value is None:
        value = {}
    if not isinstance(value, dict) or value.keys() - DEFAULTS.keys():
        raise ValueError('Choose valid pilot settings')
    settings = dict(DEFAULTS, **value)
    if settings['mode'] not in ('fixed-1', 'fixed-3', 'autoscaling') or settings['profile'] not in ('steady', 'burst'):
        raise ValueError('Choose a supported mode and profile')
    if settings['mode'] == 'autoscaling' and settings['profile'] != 'burst':
        raise ValueError('Prepared HPA pilots require the burst profile')
    for field in ('rate', 'low_rate'):
        if type(settings[field]) is not int or settings[field] <= 0:
            raise ValueError('Request rates must be positive whole numbers')
    if settings['profile'] == 'burst':
        if value.get('duration_seconds') is not None:
            raise ValueError('Burst duration is defined by workload stages')
        if settings['low_rate'] > settings['rate']:
            raise ValueError('Burst peak rate must be at least the low rate')
        settings['duration_seconds'] = None
    elif type(settings['duration_seconds']) is not int or settings['duration_seconds'] <= 0:
        raise ValueError('Steady duration must be a positive number of seconds')
    target = settings['slo_ms']
    if type(target) not in (int, float) or not math.isfinite(target) or target <= 0:
        raise ValueError('The p95 target must be a positive number of milliseconds')
    return settings


def pilot_configuration():
    workload = json.loads((ROOT / 'bench/workload.json').read_text(encoding='utf-8'))
    return dict(defaults=DEFAULTS, burst_seconds=sum(stage['seconds'] for stage in workload['burst_stages']))


def settings_arguments(settings):
    args = []
    for field in ('mode', 'profile', 'rate', 'low_rate', 'slo_ms'):
        args.extend(['--' + field.replace('_', '-'), str(settings[field])])
    if settings['duration_seconds'] is not None:
        args.extend(['--duration', f"{settings['duration_seconds']}s"])
    return args


def pilot_arguments(folder, url, activity, settings=None):
    return ['--base-url', url, '--run-dir', str(folder), *settings_arguments(pilot_settings(settings)),
            '--pilot-preparation', '--activity-note', activity]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--activity-note', required=True)
    parser.add_argument('--mode', default=DEFAULTS['mode'])
    parser.add_argument('--profile', default=DEFAULTS['profile'])
    parser.add_argument('--rate', type=int, default=DEFAULTS['rate'])
    parser.add_argument('--low-rate', type=int, default=DEFAULTS['low_rate'])
    parser.add_argument('--duration', help='Steady duration in whole seconds, such as 120s')
    parser.add_argument('--slo-ms', type=float, default=DEFAULTS['slo_ms'])
    args = parser.parse_args(argv)
    try:
        custom = {field: getattr(args, field) for field in ('mode', 'profile', 'rate', 'low_rate', 'slo_ms')}
        if args.duration is not None:
            if not args.duration.endswith('s') or not args.duration[:-1].isdigit():
                raise ValueError('Use a duration in whole seconds, such as 120s')
            custom['duration_seconds'] = int(args.duration[:-1])
        settings = pilot_settings(custom)
    except ValueError as error:
        parser.error(str(error))
    sys.path.insert(0, str(ROOT / 'bench'))
    from run_pilot import parse_arguments
    from runtime import run_command, service_url
    from run_lock import experiment_lock

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    folder = ROOT / 'results/pilot' / f'ui-{stamp}-{uuid.uuid4().hex[:6]}'
    command = [sys.executable, '-B', str(ROOT / 'bench/run_pilot.py')]
    if args.dry_run:
        planned = pilot_arguments(folder, 'http://127.0.0.1:1', args.activity_note, settings)
        parse_arguments(planned)
        seconds = settings['duration_seconds'] or pilot_configuration()['burst_seconds']
        print(f"Dry run: arguments valid. Run 1/1 · {settings['mode']} · {settings['profile']} · {settings['rate']} requests/10 s · {seconds} s.", flush=True)
        print('Service URL will be resolved at live launch. No cluster access or result files.', flush=True)
        print(subprocess.list2cmdline(command + planned), flush=True)
        return 0
    try:
        print('Run 1/1: opening Service tunnel', flush=True)
        with experiment_lock(), service_url(None) as url:
            print(f'Result: {folder.relative_to(ROOT).as_posix()}', flush=True)
            code = run_command(command + pilot_arguments(folder, url, args.activity_note, settings), folder)
        if code not in (0, 99):
            return code
        print('Run 1/1: analysis', flush=True)
        analysis = run_command([sys.executable, '-B', str(ROOT / 'bench/analyze.py'), str(folder),
                                '--output-dir', str(folder / 'analysis'), '--no-plots'])
        return analysis if analysis else code
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Pilot stopped: {error}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

"""One authorized fresh cycle with a temporary Ubuntu time-sync guard."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('C:/Users/matvi/PycharmProjects/kubernetes-autoscaling-ai-inference')
parser = argparse.ArgumentParser()
parser.add_argument('--task-name', required=True)
parser.add_argument('--series-dir', type=Path, required=True)
parser.add_argument('--launch-dir', type=Path, required=True)
args = parser.parse_args()
if not args.task_name.startswith('AI-Inference-Fresh-'):
    raise ValueError('Unexpected task name')
sys.path.insert(0, str(ROOT / 'bench'))
from run_lock import experiment_lock
from custom_metric_run import Monitor, validate_record_clock
from custom_metric_stack import render
from observe import Observer
from run_custom_series import main as run_series

sys.stdout = (args.launch_dir / 'stdout.log').open('x', encoding='utf-8', buffering=1)
sys.stderr = (args.launch_dir / 'stderr.log').open('x', encoding='utf-8', buffering=1)
state = dict(status='starting', worker_pid=os.getpid(), started_at_utc=datetime.now(timezone.utc).isoformat(),
             series_dir=str(args.series_dir), errors=[])

def save():
    target = args.launch_dir / 'worker.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)

def ubuntu(*command, check=True):
    result = subprocess.run(['wsl.exe', '-d', 'Ubuntu', '-u', 'root', '--', *command],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW)
    with (args.launch_dir / 'ubuntu-guard.log').open('a', encoding='utf-8') as log:
        log.write(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(), command=command,
                                 code=result.returncode, stdout=result.stdout, stderr=result.stderr)) + '\n')
    if check and result.returncode:
        raise RuntimeError('Ubuntu guard command failed: ' + ' '.join(command))
    return result.stdout.strip()

lease = None
lease_linux_pid = None
changed = False
initial_active = None
code = 1
lock = experiment_lock()
locked = False
try:
    save()
    lock.__enter__()
    locked = True
    if locked:
        if args.series_dir.exists():
            raise ValueError('Fresh series path already exists')
        # Keep Ubuntu alive so /run's temporary mask survives between CLI calls.
        lease = subprocess.Popen(['wsl.exe', '-d', 'Ubuntu', '--', 'sh', '-c', 'echo $$; exec sleep 28800'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        lease_linux_pid = lease.stdout.readline().strip()
        if not lease_linux_pid.isdigit():
            raise ValueError('Cannot identify the Ubuntu keep-alive process')
        initial_active = ubuntu('systemctl', 'is-active', 'systemd-timesyncd.service', check=False)
        initial_enabled = ubuntu('systemctl', 'is-enabled', 'systemd-timesyncd.service', check=False)
        state.update(ubuntu_lease_pid=lease.pid, initial_timesync_active=initial_active,
                     initial_timesync_enabled=initial_enabled)
        if initial_enabled != 'enabled' or initial_active != 'active':
            raise ValueError('Ubuntu service differs from the inspected enabled/active baseline')
        changed = True
        ubuntu('systemctl', 'mask', '--runtime', '--now', 'systemd-timesyncd.service')
        ubuntu('systemctl', 'daemon-reload')
        if (ubuntu('systemctl', 'is-enabled', 'systemd-timesyncd.service', check=False) != 'masked-runtime'
                or ubuntu('systemctl', 'is-active', 'systemd-timesyncd.service', check=False) != 'inactive'):
            raise ValueError('Temporary time-sync guard was not established')
        # Allow Docker's existing synchronizer to restore the host-relative clock.
        state['status'] = 'clock-settling'
        save()
        time.sleep(40)
        check_dir = args.launch_dir / 'clock-check'
        check_dir.mkdir()
        render(check_dir / 'inputs/custom-stack')
        monitor = Monitor(Observer(), check_dir)
        state.update(status='clock-check', clock_samples=0)
        save()
        try:
            monitor.start()
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if lease.poll() is not None:
                    raise ValueError('Ubuntu guard lease ended')
                monitor.sample()
                state['clock_samples'] += 1
                save()
                time.sleep(5)
            previous = None
            for line in (check_dir / 'custom-metric.jsonl').read_text().splitlines():
                previous = validate_record_clock(json.loads(line), previous)
        finally:
            monitor.close()
        state.update(status='running', clock_check_passed=True, clock_check_finished_at=datetime.now(timezone.utc).isoformat())
        save()
        code = run_series(['--output-dir', str(args.series_dir), '--execute'])
        state.update(status='finished' if code == 0 else 'stopped', exit_code=code)
except BaseException as error:
    state.update(status='failed', errors=[str(error)])
    print(str(error), file=sys.stderr, flush=True)
finally:
    try:
        if changed:
            ubuntu('systemctl', 'unmask', '--runtime', 'systemd-timesyncd.service')
            ubuntu('systemctl', 'daemon-reload')
            if initial_active == 'active':
                ubuntu('systemctl', 'start', 'systemd-timesyncd.service')
            state['restored_timesync_active'] = ubuntu('systemctl', 'is-active', 'systemd-timesyncd.service', check=False)
            state['restored_timesync_enabled'] = ubuntu('systemctl', 'is-enabled', 'systemd-timesyncd.service', check=False)
    except Exception as error:
        state['restoration_error'] = str(error)
    if lease is not None and lease.poll() is None:
        try:
            if lease_linux_pid and lease_linux_pid.isdigit():
                ubuntu('kill', lease_linux_pid)
            lease.wait(timeout=10)
        except Exception as error:
            state['lease_cleanup_error'] = str(error)
    if locked:
        lock.__exit__(None, None, None)
    cleanup = subprocess.run(['schtasks.exe', '/Delete', '/TN', args.task_name, '/F'],
        capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    state.update(task_cleanup_exit_code=cleanup.returncode, finished_at_utc=datetime.now(timezone.utc).isoformat())
    save()
raise SystemExit(code)

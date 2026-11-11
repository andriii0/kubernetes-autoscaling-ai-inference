"""One UI job at a time, with Windows external-run detection and saved logs."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid

from .results import read_json
from .launch import pilot_settings, settings_arguments

ROOT = Path(__file__).resolve().parent.parent


def external_runs():
    if os.name != 'nt':
        raise ValueError('Live launch requires Windows process detection')
    script = r'''[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
      $_.Name -eq 'k6.exe' -or ($_.Name -match '^python(w)?\.exe$' -and
      $_.CommandLine -match '(run_series|run_pilot|run_pilot_search|run_wait_pair|observe)\.py|lab\.launch')
    } | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress'''
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            check=True, capture_output=True, text=True, encoding='utf-8', timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    value = json.loads(result.stdout or '[]')
    return value if isinstance(value, list) else [value]


class Jobs:
    def __init__(self, results, dry_only=False):
        self.results = results
        self.dry_only = dry_only
        self.lock = threading.Lock()
        self.current = None
        self.process = None
        self.external = []
        self.scan_error = None
        self.scanned = 0
        self.scanning = threading.Lock()

    def scan(self, force=False):
        with self.scanning:
            if not force and time.monotonic() - self.scanned < 10:
                return
            try:
                self.external = external_runs()
                self.scan_error = None
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                self.external = []
                self.scan_error = f'Cannot check active experiments: {error}'
            self.scanned = time.monotonic()

    def status(self):
        self.scan()
        with self.lock:
            current = dict(self.current) if self.current else None
        external = None
        if self.external and not (current and current['active']):
            external = dict(phase='External experiment', run='—', pids=[p['ProcessId'] for p in self.external])
            for process in self.external:
                match = re.search(r'--run-dir\s+(?:"([^"]+)"|(\S+))', process.get('CommandLine') or '')
                if match:
                    folder = Path(match.group(1) or match.group(2)).resolve()
                    if folder.is_relative_to(self.results.root):
                        metadata = read_json(folder / 'metadata.json')
                        external.update(phase=metadata.get('phase') or 'Preparing', run=folder.name,
                                        result=folder.relative_to(self.results.root).as_posix())
                        break
        return dict(job=current, external=external, scan_error=self.scan_error, dry_only=self.dry_only)

    def start(self, kind, dry_run, series, activity, pilot=None):
        if kind not in ('pilot', 'series') or type(dry_run) is not bool:
            raise ValueError('Choose pilot or series and a dry-run setting')
        if self.dry_only and not dry_run:
            raise ValueError('This server is in dry-run mode')
        if not isinstance(activity, str) or not activity.strip() or len(activity) > 1000:
            raise ValueError('Describe current host activity, or enter none')
        with self.lock:
            if self.current and self.current['active']:
                raise ValueError('One launch is already active')
            if not dry_run:
                self.scan(force=True)
                if self.scan_error:
                    raise ValueError(self.scan_error)
                if self.external:
                    raise ValueError('Another experiment is running. Wait for it to finish.')
            if kind == 'pilot':
                settings = pilot_settings(pilot)
                command = [sys.executable, '-B', '-m', 'lab.launch', '--activity-note', activity.strip(),
                           *settings_arguments(settings)]
                run = '1 / 1'
            else:
                folder = self.results.path(series)
                if not folder.is_dir() or folder.parent != self.results.root / 'main':
                    raise ValueError('Select an existing main series')
                command = [sys.executable, '-B', str(ROOT / 'bench/run_series.py'), '--series-dir', str(folder),
                           '--activity-note', activity.strip()]
                run = '— / 18'
            if dry_run:
                command.append('--dry-run')
            state_dir = ROOT / '.inference-lab'
            state_dir.mkdir(exist_ok=True)
            key = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
            log_path = state_dir / f'{key}.log'
            state_path = state_dir / f'{key}.json'
            self.current = dict(id=key, kind=kind, dry_run=dry_run, active=True, phase='Checking saved data' if dry_run else 'Preparing',
                                run=run, series=series if kind == 'series' else None,
                                pilot=settings if kind == 'pilot' else None,
                                command=subprocess.list2cmdline(command), log=str(log_path), lines=[], exit_code=None)
            try:
                state_path.write_text(json.dumps(self.current, indent=2), encoding='utf-8')
                output = log_path.open('x', encoding='utf-8')
                try:
                    self.process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                    stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
                                                    env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1'))
                except BaseException:
                    output.close()
                    raise
            except OSError:
                self.current = None
                raise
            threading.Thread(target=self._watch, args=(self.process, output, state_path), daemon=True).start()
            return dict(self.current)

    def _watch(self, process, output, state_path):
        with output:
            for line in process.stdout:
                output.write(line)
                output.flush()
                text = line.strip()
                with self.lock:
                    self.current['lines'] = (self.current['lines'] + [text])[-50:]
                    if text.startswith('Starting '):
                        self.current['run'] = text.split(':', 1)[0].removeprefix('Starting ')
                        self.current['phase'] = 'Preparing'
                    if text.startswith('Result: results/'):
                        self.current['result'] = text.removeprefix('Result: results/')
                    if text.startswith(('Run 1/1:', 'attempt-', 'ui-')) and ': ' in text:
                        self.current['phase'] = text.split(': ', 1)[1]
                        if text.startswith('attempt-') and self.current.get('series'):
                            name = text.split(': ', 1)[0]
                            self.current['result'] = f"{self.current['series']}/{name}"
            code = process.wait()
            with self.lock:
                self.current.update(active=False, exit_code=code,
                                    phase='Dry run passed' if code == 0 and self.current['dry_run'] else
                                    'Finished' if code == 0 else 'Target missed' if code == 99 else 'Launch stopped')
                state_path.write_text(json.dumps(self.current, indent=2), encoding='utf-8')
        process.stdout.close()

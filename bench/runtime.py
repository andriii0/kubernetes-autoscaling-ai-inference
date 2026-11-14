"""Shared process execution, Service tunnel and pre-launch host observations."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import os
import sys
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
BOUNDARY_WARNING = 'request start within 1 ms timestamp boundary tolerance'


def run_command(command, folder=None):
    """Keep child output visible and wait for launcher cleanup after console Ctrl+C."""
    startup = None
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
    child = subprocess.Popen(command, cwd=ROOT, startupinfo=startup)
    last_phase = None
    try:
        while child.poll() is None:
            if folder and (folder / 'metadata.json').exists():
                try:
                    phase = json.loads((folder / 'metadata.json').read_text(encoding='utf-8')).get('phase')
                    if phase != last_phase:
                        print(f'{folder.name}: {phase}', flush=True)
                        last_phase = phase
                except (OSError, ValueError):
                    pass  # The launcher may be replacing the metadata while we read it.
            time.sleep(1)
        return child.returncode
    except KeyboardInterrupt:
        print('Stopping series. Waiting for the current command to finish cleanup...', flush=True)
        child.wait()
        raise


@contextmanager
def service_url(base_url):
    if base_url:
        yield base_url
        return
    if run_command(['minikube', 'start', '-p', 'ai-lab']) != 0:
        raise ValueError('Cannot resume ai-lab; check Docker Desktop and Minikube')
    with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as log:
        tunnel = subprocess.Popen(['minikube', '-p', 'ai-lab', 'service', 'ollama', '-n', 'inference', '--url'],
                                  cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                log.seek(0)
                output = log.read()
                match = re.search(r'https?://(?:127\.0\.0\.1|localhost):\d+', output)
                if match and tunnel.poll() is None:
                    print(f'Service tunnel: {match.group()}', flush=True)
                    yield match.group()
                    return
                if tunnel.poll() is not None:
                    break
                time.sleep(.5)
            raise ValueError(f'Cannot open the Service tunnel: {output}')
        finally:
            if tunnel.poll() is None:
                tunnel.terminate()
                try:
                    tunnel.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    tunnel.kill()
                    tunnel.wait()


def foreign_processes(processes, owned, executable=None):
    """Ignore owned workers and their Windows venv redirectors, not other runs."""
    owned = set(owned)
    by_id = {p["ProcessId"]: p for p in processes}
    executable = os.path.normcase(os.path.abspath(executable or sys.executable))
    for process in processes:
        if process["ProcessId"] in owned:
            parent = by_id.get(process.get("ParentProcessId"))
            if parent and parent.get("ExecutablePath") and os.path.normcase(
                    os.path.abspath(parent["ExecutablePath"])) == executable:
                owned.add(parent["ProcessId"])
    return [p for p in processes if p["ProcessId"] not in owned]


def host_snapshot():
    script = r'''$ErrorActionPreference = 'Stop'
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $p = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'k6.exe' -or $_.Name -match 'ForHonor' -or
        ($_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match '(run_series|run_pilot|run_pilot_search|run_wait_pair|run_custom_comparison|run_custom_series|prepare_custom_metric|run_peak12_comparison|resume_peak12|observe)\.py|lab\.launch')
    } | Select-Object ProcessId,ParentProcessId,ExecutablePath,Name,CommandLine)
    $cpu = @(Get-CimInstance Win32_Processor | Select-Object Name,CurrentClockSpeed,MaxClockSpeed,LoadPercentage)
    $power = powercfg /getactivescheme
    $schemeGuid = [regex]::Match(($power -join ' '), '[A-Fa-f0-9]{8}-(?:[A-Fa-f0-9]{4}-){3}[A-Fa-f0-9]{12}').Value
    if (-not $schemeGuid) { throw 'Cannot identify the active power scheme' }
    [pscustomobject]@{conflicting_processes=$p; processor_snapshot=$cpu; power_scheme_guid=$schemeGuid} | ConvertTo-Json -Depth 5'''
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                          check=True,capture_output=True,text=True,encoding='utf-8',timeout=30,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    host=json.loads(result.stdout)
    inspected=subprocess.run(['docker','inspect','ai-lab','--format','{{json .HostConfig}}'],
                              check=True,capture_output=True,text=True,timeout=15,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    config=json.loads(inspected.stdout)
    host.update(recorded_at_utc=datetime.now(timezone.utc).isoformat(),
                scope='Pre-launch snapshot; not a continuous Windows load/frequency measurement',
                minikube_container={key:config.get(key) for key in ('NanoCpus','CpuQuota','CpuPeriod','CpusetCpus','Memory')})
    from run_lock import participant_pids
    own = participant_pids()
    host['conflicting_processes'] = foreign_processes(host['conflicting_processes'], own)
    if host['conflicting_processes']:
        raise ValueError('A game or another project generator/observer is running; do not start diagnostic load')
    return host

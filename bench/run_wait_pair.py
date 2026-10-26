"""Run exactly two fixed-one diagnostics, varying only the post-warmup quiet gate."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys

import analyze
from pilot_records import timestamp
from run_series import run_command, service_url

ROOT=Path(__file__).resolve().parent.parent


def save(path, value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def host_snapshot():
    script = r'''$ErrorActionPreference = 'Stop'
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $p = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'k6.exe' -or $_.Name -match 'ForHonor' -or
        ($_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match '(run_series|run_pilot|observe)\.py')
    } | Select-Object ProcessId,Name,CommandLine)
    $cpu = @(Get-CimInstance Win32_Processor | Select-Object Name,CurrentClockSpeed,MaxClockSpeed,LoadPercentage)
    $power = powercfg /getactivescheme
    $schemeGuid = [regex]::Match(($power -join ' '), '[A-Fa-f0-9]{8}-(?:[A-Fa-f0-9]{4}-){3}[A-Fa-f0-9]{12}').Value
    if (-not $schemeGuid) { throw 'Cannot identify the active power scheme' }
    [pscustomobject]@{conflicting_processes=$p; processor_snapshot=$cpu; power_scheme_guid=$schemeGuid} | ConvertTo-Json -Depth 5'''
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                          check=True,capture_output=True,text=True,encoding='utf-8',timeout=30)
    host=json.loads(result.stdout)
    inspected=subprocess.run(['docker','inspect','ai-lab','--format','{{json .HostConfig}}'],
                              check=True,capture_output=True,text=True,timeout=15)
    config=json.loads(inspected.stdout)
    host.update(recorded_at_utc=datetime.now(timezone.utc).isoformat(),
                scope='Pre-launch snapshot; not a continuous Windows load/frequency measurement',
                minikube_container={key:config.get(key) for key in ('NanoCpus','CpuQuota','CpuPeriod','CpusetCpus','Memory')})
    if host['conflicting_processes']:
        raise ValueError('A game or another project generator/observer is running; do not start diagnostic load')
    return host


def inspect(folder):
    data=analyze.load_results(folder)
    m,check=data['metadata'],data['check']
    if not check['valid'] or m['exit_code'] not in (0,99) or m['errors']:
        raise ValueError(f'Collection/preparation failed at {folder}; retain it and inspect before another run')
    if check['counts']['unfinished'] or check['counts']['dropped']:
        raise ValueError('Incomplete request delivery/completion; no next run')
    warnings=set(check['warnings'])
    if warnings-{'request start within 1 ms timestamp boundary tolerance'}:
        raise ValueError(f'Warnings require inspection: {sorted(warnings)}')
    if m.get('protocol_version') or m.get('purpose')!='diagnostic-warmup-wait':
        raise ValueError('This result must be diagnostic evidence outside protocol v1.1')
    required={'post_load','validation','initial_quiet','recovery_quiet'}
    if not required.issubset(p['phase'] for p in m['phases']):
        raise ValueError('Required diagnostic phases are missing')
    window=check['load_window']
    if timestamp(m['scheduled_profile_finished_at_utc'])<timestamp(window['scheduled_end_at_utc']):
        raise ValueError('The scheduled profile did not finish')
    if ('post_warmup_quiet' in m)!=(m['diagnostic_warmup_wait']=='quiet'):
        raise ValueError('Recorded quiet-state gate does not match the selected variant')
    metrics=analyze.calculate_metrics(data)
    completed=[e for e in data['events'] if e['event']=='completed']
    start=timestamp(window['started_at_utc'])
    early=[e['duration_ms'] for e in completed if e['outcome']=='success' and timestamp(e['started_at_utc'])<start+30]
    changes=sorted([(timestamp(e['started_at_utc']),1) for e in data['events'] if e['event']=='started']+
                   [(timestamp(e['finished_at_utc']),-1) for e in completed])
    active=maximum=0
    for _,change in changes:
        active+=change
        maximum=max(maximum,active)
    warm=json.loads((folder/'warmup.json').read_text())
    return dict(variant=m['diagnostic_warmup_wait'],folder=str(folder.relative_to(ROOT)),
                collection_valid=check['valid'],counts=check['counts'],warnings=sorted(warnings),
                p95_ms=metrics['p95_ms'],mean_ms=metrics['mean_ms'],max_ms=metrics['max_ms'],
                p95_target_pass=metrics['p95_ms']<=5000 if metrics['p95_ms'] is not None else None,
                first_30s_mean_ms=sum(early)/len(early) if early else None,max_client_in_flight=maximum,
                post_warmup_delay_seconds=start-timestamp(warm['finished_at_utc']),warmup=warm,
                initial_identity=m['initial_identity'],runtime_context=m['runtime_context'],
                source_sha256=m['source_sha256'],workload=m['workload'],settings={key:m[key] for key in
                    ('rate','profile','duration_seconds','idle_seconds','post_seconds','observer_interval_seconds','slo_ms')},
                output_tokens=dict(Counter(str(e.get('output_tokens')) for e in completed)))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    series=args.series_dir.resolve()
    series.mkdir(parents=True,exist_ok=False)
    variants=['immediate','quiet']
    random.SystemRandom().shuffle(variants)
    manifest=dict(purpose='diagnostic-warmup-wait',started_at_utc=datetime.now(timezone.utc).isoformat(),
                  order=variants,order_method='one random draw before the first run',
                  planned_runs=2,completed_runs=0,status='preparing',
                  fixed_settings={'replicas':1,'hpa':False,'rate_per_10s':8,'duration_seconds':300,
                                  'idle_seconds':60,'post_seconds':10,'observer_interval_seconds':5,'slo_ms':5000},
                  limitation='One pair is a screen; order/host drift prevents a general causal conclusion')
    save(series/'manifest.json',manifest)
    shutil.copyfile(__file__,series/'run_wait_pair.py')
    manifest['runner_sha256']=hashlib.sha256((series/'run_wait_pair.py').read_bytes()).hexdigest()
    save(series/'manifest.json',manifest)
    rows=[]
    try:
        with service_url(None) as url:
            for order,variant in enumerate(variants,1):
                host=host_snapshot()
                save(series/f'{order:02d}-{variant}-host-before.json',host)
                folder=series/f'{order:02d}-{variant}'
                command=[sys.executable,'-B',str(ROOT/'bench/run_pilot.py'),'--mode','fixed-1','--profile','steady',
                         '--diagnostic-warmup-wait',variant,'--rate','8','--duration','5m','--slo-ms','5000',
                         '--base-url',url,'--run-dir',str(folder),'--activity-note',
                         'No For Honor or other project k6/observer found before launch; see the pre-launch host snapshot.']
                print(f'Diagnostic {order}/2: {variant}',flush=True)
                code=run_command(command,folder)
                if code not in (0,99):
                    raise ValueError(f'Launcher exit {code}; no next run. Evidence: {folder}')
                row=inspect(folder)
                if rows:
                    for key in ('source_sha256','workload','settings','initial_identity'):
                        if row[key]!=rows[0][key]:
                            raise ValueError(f'Pair setting/identity changed: {key}; results require manual review')
                    previous=rows[0]['runtime_context']
                    if ({m['digest'] for m in row['runtime_context']['models'].values()}!=
                            {m['digest'] for m in previous['models'].values()}):
                        raise ValueError('Model identity differs between variants')
                if analyze.main([str(folder),'--output-dir',str(series/f'{order:02d}-{variant}-analysis'),'--no-plots']):
                    raise ValueError('Analysis failed; no next run')
                rows.append(row)
                save(series/'comparison.json',rows)
                manifest.update(completed_runs=len(rows),status='running' if len(rows)<2 else 'finished')
                save(series/'manifest.json',manifest)
                print(f"Saved {variant}: p95={row['p95_ms']} ms, post-warmup delay={row['post_warmup_delay_seconds']:.3f} s",flush=True)
        manifest['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        save(series/'manifest.json',manifest)
        print('Two diagnostic runs complete. No further load is scheduled.',flush=True)
        return 0
    except (OSError,ValueError,KeyError,subprocess.SubprocessError,KeyboardInterrupt) as error:
        manifest.update(status='stopped',error=str(error),finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(series/'manifest.json',manifest)
        print(f'Diagnostic stopped: {error}',flush=True)
        return 1


if __name__=='__main__':
    raise SystemExit(main())

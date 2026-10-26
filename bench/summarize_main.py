"""Replay a complete v1.1 matrix and compare repetitions without changing saved runs."""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics

import analyze
import main_protocol
from pilot_records import read_jsonl, timestamp


def write_csv(path, rows):
    with path.open('x', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def compare(series, output, plots=True):
    folders = [series / f"attempt-{r['planned_order']:02d}-{r['mode']}-{r['profile']}"
               for r in main_protocol.matrix()]
    rows, instances, nodes, scaling, phases, checks, source_hashes = [], [], [], [], [], [], {}
    workloads, model_ids, image_ids, runtime_settings = set(), set(), set(), set()
    for folder, expected in zip(folders, main_protocol.matrix()):
        data = analyze.load_results(folder)
        metadata, check = data['metadata'], data['check']
        if any(metadata.get(key) != value for key, value in dict(expected, actual_order=expected['planned_order']).items()):
            raise ValueError(f'{folder.name}: matrix identity mismatch; review manually')
        assessment = json.loads(json.dumps(main_protocol.assessment(data)))
        resources = main_protocol.primary_resources(data)
        saved = series / f"attempt-{expected['planned_order']:02d}-analysis"
        for name, replay in (('assessment.json', assessment),):
            if json.loads((folder / name).read_text()) != replay:
                raise ValueError(f'{folder.name}: saved assessment differs')
        for name, replay in (('primary-resources.json', resources), ('assessments.json', assessment)):
            if json.loads((saved / name).read_text())[folder.name] != replay:
                raise ValueError(f'{folder.name}: saved {name} differs')
        if (not assessment['data_valid'] or not assessment['duration_complete'] or assessment['unfinished'] != 0
                or assessment['dropped'] != 0 or metadata.get('exit_code') not in (0, 99)):
            raise ValueError(f'{folder.name}: incomplete evidence; retain it and review manually')
        for name, digest in metadata['source_sha256'].items():
            actual = hashlib.sha256((folder / 'inputs' / name).read_bytes()).hexdigest()
            if actual.lower() != digest.lower():
                raise ValueError(f'{folder.name}: archived input mismatch: {name}')
            source_hashes.setdefault(name, set()).add(actual)
        workloads.add(json.dumps(metadata['workload'], sort_keys=True))
        context = metadata['runtime_context']
        model_ids.update(model['digest'] for model in context['models'].values())
        initial = metadata['initial_identity']
        image_ids.update(item['image_id'] for item in (initial if isinstance(initial, list) else [initial]))
        runtime_settings.add(json.dumps({'profile_cpu': context['minikube_profile']['Config']['CPUs'],
            'profile_memory': context['minikube_profile']['Config']['Memory'],
            'docker_engine': context['docker_limits']}, sort_keys=True))
        start = timestamp(check['load_window']['started_at_utc'])
        end = timestamp(check['load_window']['scheduled_end_at_utc'])
        events = [e for e in data['events'] if e['event'] == 'completed']
        starts = {e['request_id']: e for e in data['events'] if e['event'] == 'started'}
        primary = [e for e in events if metadata['profile'] == 'steady' or
                   121 <= timestamp(starts[e['request_id']]['started_at_utc']) - start < 421]
        values = sorted(e['duration_ms'] for e in primary if e['outcome'] == 'success')
        if not values:
            raise ValueError(f'{folder.name}: no successful primary responses; preserve the outcome and review manually')
        index = (len(values) - 1) * .95
        lower = int(index)
        independent_p95 = values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (index - lower)
        if abs(independent_p95 - assessment['primary']['p95_ms']) > 1e-6:
            raise ValueError(f'{folder.name}: primary p95 does not match independent calculation')
        primary_raw = [p['data']['value'] for p in read_jsonl(folder / 'requests.json')
                       if p.get('type') == 'Point' and p.get('metric') == 'primary_successful_latency_ms']
        if sorted(primary_raw) != values:
            raise ValueError(f'{folder.name}: raw k6 primary latency differs from request-start assignment')
        metrics = analyze.calculate_metrics(data)
        if json.loads((saved / 'analysis.json').read_text())[0] != metrics:
            raise ValueError(f'{folder.name}: saved whole-run summary differs')
        times = [timestamp(s['time']) for s in data['cluster']]
        if not all(b > a for a, b in zip(times, times[1:])):
            raise ValueError(f'{folder.name}: observation times are not strictly increasing')
        ready = lambda s: sum(not p['metadata'].get('deletionTimestamp') and
            any(c['type'] == 'Ready' and c['status'] == 'True' for c in p.get('status', {}).get('conditions', []))
            for p in s['pods']['items'])
        selected = [s for s in data['cluster'] if start <= timestamp(s['time']) <= end]
        ready_seconds = sum(ready(a) * max(0, min(end, timestamp(b['time'])) - max(start, timestamp(a['time'])))
                            for a, b in zip(data['cluster'], data['cluster'][1:]))
        active = [r for r in resources['instances'] if r['expected_seconds'] is None or r['expected_seconds'] > 0]
        node = resources['nodes'][0]
        warnings = sorted(set(check['warnings']))
        row = dict(run=folder.name, **expected, load_start_utc=check['load_window']['started_at_utc'],
            source_commit=metadata['source_revision']['commit'], **check['counts'],
            primary_successful=assessment['primary']['successful'], primary_failed=assessment['primary']['failed'],
            primary_p95_ms=independent_p95, primary_max_ms=max(values),
            primary_over_5000_ms=sum(v > 5000 for v in values), whole_p95_ms=metrics['p95_ms'],
            whole_max_ms=metrics['max_ms'], whole_over_5000_ms=sum(e['duration_ms'] > 5000 for e in events),
            data_valid=assessment['data_valid'], duration_complete=assessment['duration_complete'],
            primary_p95_pass=assessment['primary_p95_pass'], primary_errors_pass=assessment['primary_errors_pass'],
            whole_run_errors_pass=assessment['whole_run_errors_pass'], sensitivity_p95_pass=assessment['sensitivity_p95_pass'],
            overall=assessment['overall'], scaling_observed=assessment['scaling_observed'],
            ready_min=min(map(ready, selected)), ready_max=max(map(ready, selected)),
            ready_copy_seconds_estimate=ready_seconds, ready_mean_estimate=ready_seconds/(end-start),
            application_cpu_core_seconds_estimate=resources['application_cpu_core_seconds_estimate'],
            application_cpu_complete=resources['application_cpu_core_seconds_estimate'] is not None,
            node_cpu_core_seconds_estimate=node['cpu_core_seconds_estimate'], node_cpu_full_coverage=node['cpu_full_coverage'],
            node_observed_peak_memory_mib=node['observed_peak_memory_mib'],
            smallest_instance_cpu_coverage=min(r['cpu_coverage'] for r in active if r['cpu_coverage'] is not None),
            distribution_counts=json.dumps(check.get('distribution', {}).get('pods', {}), sort_keys=True),
            largest_model_load_ms=max(e.get('model_load_ms') or 0 for e in events),
            output_token_counts=json.dumps(Counter(e.get('output_tokens') for e in events), sort_keys=True),
            warnings='; '.join(warnings))
        rows.append(row)
        for kind, records in ((instances, active), (nodes, resources['nodes'])):
            for record in records:
                kind.append(dict(run=folder.name, mode=metadata['mode'], profile=metadata['profile'], repetition=metadata['repetition'], **record))
        for phase in main_protocol.phase_results(data):
            phases.append(dict(run=folder.name, mode=metadata['mode'], profile=metadata['profile'], repetition=metadata['repetition'],
                               **{k:v for k,v in phase.items() if k != 'failure_categories'}))
        if metadata['mode'] == 'autoscaling':
            detail = analyze.scaling_details(data)
            for direction in ('growth', 'reduction'):
                transition = next((c for c in detail['changes'] if c['direction'] == direction), None)
                scaling.append(dict(run=folder.name, profile=metadata['profile'], repetition=metadata['repetition'],
                    direction=direction, requested_seconds=transition['requested_seconds'] if transition else None,
                    running_matches_seconds=transition['running_matches_seconds'] if transition else None,
                    from_count=transition['from'] if transition else None, to_count=transition['to'] if transition else None))
        checks.append(dict(run=folder.name, errors=check['errors'], warnings=warnings, observation=check['observation'],
                           independent_primary_p95_matches=True, raw_k6_primary_latencies_match=True,
                           saved_assessment_and_resources_match=True, system_outcomes=assessment['system_outcomes']))
        print(f"Checked {folder.name}: {assessment['overall']}", flush=True)
    if (any(len(v) != 1 for v in source_hashes.values()) or len(workloads) != 1 or len(model_ids) != 1
            or len(image_ids) != 1 or len(runtime_settings) != 1):
        raise ValueError('Input/runtime identities differ between attempts; review before comparison')
    args = [str(folder) for folder in folders] + ['--output-dir', str(output)]
    if not plots:
        args.append('--no-plots')
    if analyze.main(args) != 0:
        raise ValueError('Existing analyzer failed; preserve its partial output')
    groups = []
    for profile in ('steady', 'burst'):
        for mode in ('fixed-1', 'fixed-3', 'autoscaling'):
            selected = sorted((r for r in rows if (r['mode'], r['profile']) == (mode, profile)), key=lambda r:r['repetition'])
            p95s = [r['primary_p95_ms'] for r in selected]
            groups.append(dict(mode=mode, profile=profile, repetitions=len(selected),
                p95_repeat_1_ms=p95s[0], p95_repeat_2_ms=p95s[1], p95_repeat_3_ms=p95s[2],
                median_of_run_p95_ms=statistics.median(p95s), min_run_p95_ms=min(p95s), max_run_p95_ms=max(p95s),
                target_pass_repetitions=sum(r['overall']=='pass' for r in selected),
                completed=sum(r['completed'] for r in selected), failed=sum(r['failed'] for r in selected),
                unfinished=sum(r['unfinished'] for r in selected), dropped=sum(r['dropped'] for r in selected),
                application_cpu_full_repetitions=sum(r['application_cpu_complete'] for r in selected),
                median_node_cpu_core_seconds=statistics.median(r['node_cpu_core_seconds_estimate'] for r in selected)
                    if all(r['node_cpu_full_coverage'] for r in selected) else None,
                median_ready_mean_estimate=statistics.median(r['ready_mean_estimate'] for r in selected)))
    for filename, records in (('main-runs.csv', rows), ('mode-profile.csv', groups), ('primary-instances.csv', instances),
                               ('primary-nodes.csv', nodes), ('scaling-transitions.csv', scaling), ('primary-phases.csv', phases)):
        write_csv(output / filename, records)
    (output / 'validation.json').write_text(json.dumps(dict(runs=checks, source_sha256={k:next(iter(v)) for k,v in source_hashes.items()},
        model_digests=sorted(model_ids), image_ids=sorted(image_ids), runtime_settings=[json.loads(s) for s in runtime_settings]), indent=2)+'\n')
    if plots:
        import matplotlib.pyplot as plt
        colors = {'fixed-1':'#2463a2','fixed-3':'#ad6a22','autoscaling':'#687e36'}
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout='constrained', sharey=True)
        for ax, profile in zip(axes, ('steady', 'burst')):
            for x, mode in enumerate(colors):
                selected = [r for r in groups if (r['mode'],r['profile'])==(mode,profile)][0]
                values = [selected[f'p95_repeat_{i}_ms']/1000 for i in (1,2,3)]
                ax.scatter([x-.12,x,x+.12], values, c=colors[mode], marker='o', s=50)
                for dx, value, repetition in zip((-.12,0,.12),values,(1,2,3)):
                    ax.annotate(str(repetition),(x+dx,value),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
            ax.axhline(5, color='#444444', linestyle='--', linewidth=1, label='Primary target: 5 s')
            ax.set_xticks(range(3),list(colors))
            ax.set_title('Steady: full 300 s' if profile=='steady' else 'Burst: peak [121, 421) s')
            ax.set_ylim(0,5.6)
            ax.grid(axis='y',alpha=.2)
            ax.legend(loc='upper right',fontsize=8)
        axes[0].set_ylabel('Successful-response p95 (s)')
        fig.suptitle('Every repetition; labels 1-3 identify runs, not confidence intervals')
        for ext in ('png','svg'):
            fig.savefig(output / f'primary-p95.{ext}', dpi=160)
        plt.close(fig)
    method = '''# Completed main-series analysis

All 18 planned cells are included. See main-runs.csv for individual runs and mode-profile.csv for all three p95 values and their median. A median of run p95 values is not a pooled request percentile. Request counts and primary phases remain explicit. Raw files and existing per-attempt outputs are read only.

To reproduce from the repository root, select a new output directory:

```powershell
.\\.venv\\Scripts\\python.exe -B bench/summarize_main.py results/main/series-2026-10-25-v1.1 --output-dir results/main/series-2026-10-25-v1.1/analysis-rerun
```

The command writes the group/run/resource/phase/scaling CSV files, replay validation and PNG/SVG plots. It refuses an existing destination. --no-plots retains all CSV/JSON outputs without Matplotlib.

The existing analyzer produces the aligned per-run latency/outcome/Ready/CPU/memory plots and historical whole-run summary. These use completion timestamps for plotted points; primary phases use request-start membership in primary-phases.csv and the primary-p95 plot. All points in that plot are actual repetitions. The 5-second target applies to primary successful p95, not every individual response. Error acceptance is assessed separately.

CPU core-seconds are source-interval estimates for the scheduled window only. Incomplete application totals remain empty. Per-instance observed memory peaks are not summed. Node data includes Kubernetes and is not added to application consumption. Ready copy-seconds use a left-step interpolation of observed state; they describe available capacity, not CPU consumption, reservation or cost.

Frozen workload/input hashes, initial model digests/image IDs and recorded runtime fields match. The docker_limits field was obtained from docker info: it describes the engine scope, not an independently inspected Minikube-container quota. Profile settings and Kubernetes capacity are separate scopes.

The series spans interruptions and a cluster restart before attempt 11. Repetition 2 steady straddles that restart. Main targets were retained, while the severe historical pilot degradation did not repeat; these data do not isolate its cause. Shared-host drift, repeated prompt/prefix caching, a small model and three repetitions limit causal or production conclusions. Keep all outcomes; do not retune this series to force a scaling benefit.

validation.json records replay results and warnings. Target passes do not establish an HPA advantage or full resource coverage. Normal server drain, Windows-wide energy and monetary savings are not verified. The final Notion findings and reproduction review remain separate project steps.
'''
    (output / 'README.md').write_text(method,encoding='utf-8')
    return rows, groups


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('series', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        parser.error('output directory already exists; choose a new path')
    try:
        compare(args.series.resolve(), args.output_dir.resolve(), not args.no_plots)
        return 0
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        print(f'Main comparison failed: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

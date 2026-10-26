"""Compare saved pilot and fixed-one runs; print evidence without contacting the cluster."""

from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import statistics
import sys

ROOT=next((p for p in Path(__file__).resolve().parents if (p/'bench/pilot_records.py').is_file()),None)
if ROOT is None:
    raise RuntimeError('Keep this evidence script inside the project checkout')
sys.path.insert(0,str(ROOT/'bench'))
import analyze
from pilot_records import timestamp


def percentile(values,p=.95):
    values=sorted(values)
    if not values:
        return None
    position=(len(values)-1)*p
    left=int(position)
    return values[left]+(values[min(left+1,len(values)-1)]-values[left])*(position-left)


def inspect(folder):
    data=analyze.load_results(folder)
    m,check=data['metadata'],data['check']
    assert check['valid'],check['errors']
    for name,digest in m['source_sha256'].items():
        assert hashlib.sha256((folder/'inputs'/name).read_bytes()).hexdigest().lower()==digest.lower()
    start=timestamp(check['load_window']['started_at_utc'])
    end=start+m['duration_seconds']
    starts=sorted((e for e in data['events'] if e['event']=='started'),key=lambda e:timestamp(e['started_at_utc']))
    complete=sorted((e for e in data['events'] if e['event']=='completed'),key=lambda e:timestamp(e['finished_at_utc']))
    success=[e for e in complete if e['outcome']=='success']
    chronological=sorted([(timestamp(e['started_at_utc']),1) for e in starts]+
                         [(timestamp(e['finished_at_utc']),-1) for e in complete])
    active=max_active=0
    for _,change in chronological:
        active+=change
        max_active=max(max_active,active)
    assert active==0
    early=[e['duration_ms'] for e in success if timestamp(e['started_at_utc'])<start+30]
    windows=[]
    for offset in range(0,int(m['duration_seconds']),30):
        selected=[e for e in complete if start+offset<=timestamp(e['started_at_utc'])<start+offset+30]
        outcomes=[e['duration_ms'] for e in selected if e['outcome']=='success']
        unfinished_at_end=sum(timestamp(e['started_at_utc'])<=start+offset+30 for e in starts)-sum(timestamp(e['finished_at_utc'])<=start+offset+30 for e in complete)
        windows.append(dict(run=folder.name,start_second=offset,completed=len(selected),failed=sum(e['outcome']!='success' for e in selected),
                            mean_success_ms=statistics.mean(outcomes) if outcomes else None,p95_success_ms=percentile(outcomes),
                            client_in_flight_at_window_end=unfinished_at_end))
    saturated_gaps=[]
    ordered=sorted(complete,key=lambda e:timestamp(e['finished_at_utc']))
    for previous,current in zip(ordered,ordered[1:]):
        a,b=timestamp(previous['finished_at_utc']),timestamp(current['finished_at_utc'])
        if start+30<=a<b<=end and all(e['outcome']=='success' for e in (previous,current)):
            in_flight=sum(timestamp(e['started_at_utc'])<=a for e in starts)-sum(timestamp(e['finished_at_utc'])<=a for e in complete)
            if in_flight>=2:
                saturated_gaps.append((b-a)*1000)
    cpu=[r['cpu_cores'] for sample in data['cluster'] if start<=timestamp(sample['time'])<=end
         for r in sample['resource_usage'] if r['scope']=='container' and r.get('cpu_cores') is not None]
    http_diff=[e['duration_ms']-e['http_duration_ms'] for e in complete if e.get('http_duration_ms') is not None]
    versions={}
    for tool,record in m['versions'].items():
        stdout=record.get('stdout','')
        if tool=='docker' and stdout:
            d=json.loads(stdout)
            versions[tool]=(d['Client']['Version'],d['Server']['Version'])
        elif tool=='kubectl' and stdout:
            d=json.loads(stdout)
            versions[tool]=(d.get('clientVersion',{}).get('gitVersion'),d.get('serverVersion',{}).get('gitVersion'))
        elif tool=='minikube' and stdout:
            versions[tool]=json.loads(stdout).get('minikubeVersion')
        else:
            versions[tool]=stdout or record
    container=next(c for c in m['deployment_snapshot']['spec']['template']['spec']['containers'] if c['name']=='ollama')
    warmup=json.loads((folder/'warmup.json').read_text())
    initial=m['initial_identity']
    row=dict(run=folder.name,kind='main' if m.get('protocol_version') else 'pilot',rate_per_10s=m['rate'],profile=m['profile'],
             duration_seconds=m['duration_seconds'],**check['counts'],mean_success_ms=statistics.mean(e['duration_ms'] for e in success),
             p95_success_ms=percentile([e['duration_ms'] for e in success]),first_30s_mean_success_ms=statistics.mean(early),
             max_client_in_flight=max_active, median_start_gap_ms=statistics.median((timestamp(b['started_at_utc'])-timestamp(a['started_at_utc']))*1000 for a,b in zip(starts,starts[1:])),
             median_busy_completion_gap_ms=statistics.median(saturated_gaps) if saturated_gaps else None,
             busy_completion_gap_samples=len(saturated_gaps),cpu_sample_mean_cores=statistics.mean(cpu),cpu_sample_max_cores=max(cpu),
             cpu_fresh_source_mean_cores=analyze.calculate_metrics(data)['cpu_mean_cores'],
             median_elapsed_minus_http_ms=statistics.median(http_diff),warmup_ms=warmup['duration_ms'],
             mean_model_load_ms=statistics.mean(e['model_load_ms'] for e in success if e['model_load_ms'] is not None),
             max_model_load_ms=max(e['model_load_ms'] for e in success if e['model_load_ms'] is not None),
             output_tokens=json.dumps(Counter(e['output_tokens'] for e in success),sort_keys=True),
             image_id=initial['image_id'],request=m['workload']['request'],container=container,versions=versions,
             idle_before_warmup_seconds=m['idle_seconds'],load_start_delay_after_warmup_s=timestamp(check['load_window']['started_at_utc'])-timestamp(warmup['finished_at_utc']))
    print(json.dumps({k:v for k,v in row.items() if k not in ('request','container','versions')}),flush=True)
    return row,windows


def main():
    pilot=ROOT/'results/pilot/discovery-2026-10-18-series1'
    main=ROOT/'results/main/series-2026-10-25-v1.1'
    folders=[pilot/n for n in ('A2-rate-2','B-rate-5','C-rate-10','M-rate-8','confirm-low-1','confirm-peak-1','confirm-low-2','confirm-peak-2')]
    folders += [main/n for n in ('attempt-01-fixed-1-steady','attempt-12-fixed-1-steady','attempt-14-fixed-1-steady')]
    rows,windows=[],[]
    for folder in folders:
        row,phase=inspect(folder)
        rows.append(row)
        windows+=phase
    reference=rows[0]
    assert all(r['request']==reference['request'] for r in rows)
    assert len({r['image_id'] for r in rows})==1
    for r in rows:
        assert r['versions']==reference['versions'],(r['run'],'recorded versions differ')
        for key in ('resources','env','image','imagePullPolicy'):
            assert r['container'][key]==reference['container'][key],(r['run'],key)
    if len(sys.argv)>1:
        out=Path(sys.argv[1])
        out.mkdir(parents=True,exist_ok=False)
        (out/'comparison.json').write_text(json.dumps(dict(runs=rows,windows=windows),indent=2)+'\n',encoding='utf-8')
        numeric=[{k:v for k,v in r.items() if k not in ('request','container','versions')} for r in rows]
        for name,records in (('comparison.csv',numeric),('latency-windows.csv',windows)):
            with (out/name).open('x',encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(records[0]))
                writer.writeheader()
                writer.writerows(records)
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True,layout='constrained')
        labels={'confirm-peak-1':('Pilot peak 1','#b36b24','o'),
                'confirm-peak-2':('Pilot peak 2','#d49a4a','s'),
                'attempt-01-fixed-1-steady':('Main repeat 1','#2463a2','o'),
                'attempt-12-fixed-1-steady':('Main repeat 2','#4589c5','s'),
                'attempt-14-fixed-1-steady':('Main repeat 3','#6ba6cd','^')}
        for folder in folders:
            if folder.name not in labels:
                continue
            label,color,marker=labels[folder.name]
            d=analyze.load_results(folder)
            start=timestamp(d['check']['load_window']['started_at_utc'])
            e=[e for e in d['events'] if e['event']=='completed' and e['outcome']=='success']
            axes[0].scatter([timestamp(e['started_at_utc'])-start for e in e],[e['duration_ms']/1000 for e in e],
                            s=9,alpha=.7,label=label,color=color,marker=marker)
            changes=sorted([(timestamp(e['started_at_utc'])-start,1) for e in d['events'] if e['event']=='started']+
                           [(timestamp(e['finished_at_utc'])-start,-1) for e in d['events'] if e['event']=='completed'])
            active=0
            times,counts=[0],[0]
            for at,change in changes:
                active+=change
                times.append(at)
                counts.append(active)
            axes[1].step(times,counts,where='post',color=color,label=label,linewidth=1.2)
        axes[0].set_ylabel('Successful response latency (s)')
        axes[1].set_ylabel('Client requests in flight')
        axes[1].set_xlabel('Seconds from scenario start; same offered rate: 8 requests / 10 s')
        axes[0].legend(ncol=3,fontsize=8,loc='upper left')
        for ax in axes:
            ax.axvline(300,color='#666666',linestyle='--',linewidth=1)
            ax.set_ylim(bottom=0)
            ax.grid(axis='y',alpha=.2)
        axes[0].set_title('Pilot waiting accumulated; main fixed-one runs had little overlap',loc='left')
        for ext in ('png','svg'):
            fig.savefig(out/f'queue-comparison.{ext}',dpi=160)
        plt.close(fig)
    print('Request payload, container resources/environment/image, image ID and archive hashes checked for all selected runs.')


if __name__=='__main__':
    main()

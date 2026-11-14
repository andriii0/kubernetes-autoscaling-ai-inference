"""One manually started Windows task; independent of the Codex process tree."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

root=Path('C:/Users/matvi/PycharmProjects/kubernetes-autoscaling-ai-inference')
parser=argparse.ArgumentParser()
parser.add_argument('--task-name',required=True)
parser.add_argument('--series-dir',required=True,type=Path)
parser.add_argument('--launch-dir',required=True,type=Path)
args=parser.parse_args()
assert args.task_name.startswith('AI-Inference-Fresh-')
record=dict(status='starting',worker_pid=os.getpid(),parent_pid=os.getppid(),
            started_at_utc=datetime.now(timezone.utc).isoformat(),series_dir=str(args.series_dir))
def save():
    p=args.launch_dir/'worker.json'
    temp=p.with_suffix('.tmp')
    temp.write_text(json.dumps(record,indent=2)+'\n')
    temp.replace(p)
code=1
try:
    if args.series_dir.exists(): raise ValueError('Fresh series directory already exists')
    command=[str(root/'.venv/Scripts/python.exe'),'-B','bench/run_custom_series.py',
             '--output-dir',str(args.series_dir),'--execute']
    record['command']=command
    with (args.launch_dir/'stdout.log').open('x') as out,(args.launch_dir/'stderr.log').open('x') as err:
        child=subprocess.Popen(command,cwd=root,stdout=out,stderr=err,
                               creationflags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP)
        record.update(status='running',launcher_pid=child.pid)
        save()
        code=child.wait()
        record.update(status='finished' if code==0 else 'stopped',exit_code=code)
except Exception as error:
    record.update(status='failed',error=str(error))
finally:
    record['finished_at_utc']=datetime.now(timezone.utc).isoformat()
    cleanup=subprocess.run(['schtasks.exe','/Delete','/TN',args.task_name,'/F'],capture_output=True,text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    record['task_cleanup_exit_code']=cleanup.returncode
    if cleanup.returncode: record['task_cleanup_error']=cleanup.stderr.strip()
    save()
raise SystemExit(code)

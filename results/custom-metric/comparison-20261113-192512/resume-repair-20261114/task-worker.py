"""Run the authorized remaining cells as a child of the Windows task service."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path("C:/Users/matvi/PycharmProjects/kubernetes-autoscaling-ai-inference")
SERIES = ROOT / "results/custom-metric/comparison-20261113-192512"


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(value, indent=2), encoding="utf-8")
    pending.replace(path)


parser = argparse.ArgumentParser()
parser.add_argument("--task-name", required=True)
parser.add_argument("--record-path", required=True, type=Path)
args = parser.parse_args()
record_path = args.record_path.resolve()
record = {
    "task_name": args.task_name,
    "started_at_utc": now(),
    "worker_pid": os.getpid(),
    "worker_parent_pid": os.getppid(),
    "series_dir": str(SERIES),
    "launch_method": "Direct Python action in a manually started Windows task; current account, limited privileges.",
    "recurring_triggers": 0,
}
command = [
    str(ROOT / ".venv/Scripts/python.exe"), "-B", "bench/run_custom_comparison.py",
    "--preparation-dir", "results/custom-metric/preparation-20261113-165340",
    "--output-dir", str(SERIES), "--resume", "--execute",
    "--recovered-infrastructure-record", str(SERIES / "resume-repair-20261114/host-recovery/infrastructure-recovery.json"),
]
exit_code = 1
try:
    manifest = json.loads((SERIES / "manifest.json").read_text())
    if manifest["status"] != "stopped" or len(manifest["completed"]) != 4:
        raise RuntimeError("The preserved stopped four-cell prefix is required")
    if (SERIES / "resume.lock").exists():
        raise RuntimeError("A continuation lock already exists")
    stdout_path = record_path.with_suffix(".stdout.log")
    stderr_path = record_path.with_suffix(".stderr.log")
    record.update(stdout=str(stdout_path), stderr=str(stderr_path), command=command)
    with stdout_path.open("x", encoding="utf-8") as output, stderr_path.open("x", encoding="utf-8") as error:
        child = subprocess.Popen(
            command, cwd=ROOT, stdout=output, stderr=error,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        record["launcher_pid"] = child.pid
        save(record_path, record)
        for _ in range(30):
            if child.poll() is not None:
                break
            try:
                current = json.loads((SERIES / "manifest.json").read_text())
                if current["pid"] != manifest["pid"] and current["status"] in ("starting", "running"):
                    record["driver_pid"] = current["pid"]
                    save(record_path, record)
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        exit_code = child.wait()
        record["exit_code"] = exit_code
except Exception as error:
    record["worker_error"] = str(error)
finally:
    record["finished_at_utc"] = now()
    cleanup = subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", args.task_name, "/F"],
        capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    record["task_cleanup_exit_code"] = cleanup.returncode
    if cleanup.returncode:
        record["task_cleanup_error"] = cleanup.stderr.strip()
    save(record_path, record)
raise SystemExit(exit_code)


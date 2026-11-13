"""Run only the two authorized custom-metric threshold preparations, in new paths."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from analyze import assessment, load_results, main as analyze, phase_results
from autoscaling import ready, target_hpa
from records import timestamp
from run_pilot import parse_arguments
from runtime import BOUNDARY_WARNING, host_snapshot, run_command

ROOT = Path(__file__).resolve().parent.parent


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def arguments(folder, target, url):
    return ["--pilot-preparation", "--custom-metric-policy", f"active-{target}",
            "--mode", "autoscaling", "--profile", "burst", "--rate", "12", "--low-rate", "2",
            "--slo-ms", "5000", "--base-url", url, "--run-dir", str(folder),
            "--activity-note", "Separate active-request threshold preparation; host snapshot saved by driver."]


@contextmanager
def gateway_url(folder):
    with (folder / "gateway-tunnel.log").open("w+", encoding="utf-8") as log:
        command = ["kubectl", "--context", "ai-lab", "-n", "inference", "port-forward",
                   "--address=127.0.0.1", "service/inference-gateway", ":8080"]
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        save(folder / "gateway-tunnel.json", {"pid": process.pid, "command": command, "started_at": now()})
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                log.seek(0)
                output = log.read()
                match = re.search(r"Forwarding from 127\.0\.0\.1:(\d+)", output)
                if match and process.poll() is None:
                    yield f"http://127.0.0.1:{match[1]}"
                    return
                if process.poll() is not None:
                    break
                time.sleep(.2)
            raise RuntimeError("gateway tunnel did not become available; see gateway-tunnel.log")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def qualify(data):
    """Judge mechanism/stability, never select on response latency."""
    start = timestamp(data["check"]["load_window"]["started_at_utc"])
    points = []
    for sample in data["cluster"]:
        at = timestamp(sample["time"]) - start
        hpa = target_hpa(sample, "ollama")
        if hpa:
            desired = hpa.get("status", {}).get("desiredReplicas")
            count = sum(ready(p) for p in sample["pods"]["items"])
            if type(desired) is not int:
                raise ValueError("missing HPA desired count in preparation")
            points.append((at, desired, count))
    prior = [p for p in points if p[0] <= 0]
    observed = [p for p in points if 0 < p[0] < 421]
    after = [p for p in points if p[0] >= 421]
    if not prior or not after:
        raise ValueError("missing observations around the low/peak window")
    covered = [prior[-1], *observed, after[0]]
    if any(not 0 < b[0] - a[0] <= 10 for a, b in zip(covered, covered[1:])):
        raise ValueError("preparation replica observations have a gap above 10 seconds")
    low = [p for p in covered if p[0] < 120]
    peak = [p for p in covered if 121 <= p[0] < 421]
    stable = bool(low) and all(p[1:] == (1, 1) for p in low)
    desired = next((p[0] for p in peak if p[1] >= 2), None)
    available = next((p[0] for p in peak if p[2] >= 2), None)
    return {"qualifies": stable and desired is not None and available is not None,
            "initial_low_one_copy": stable, "peak_desired_two_at_seconds": desired,
            "peak_ready_two_at_seconds": available,
            "scope": "Sampled at 5s; gaps over 10s invalidate qualification. Latency is not a selection criterion."}


def select(results):
    if [r["target"] for r in results] != [1, 2]:
        raise ValueError("both preparation targets must have valid collected evidence")
    return next((r["target"] for r in results if r["qualification"]["qualifies"]), None)


def review(folder, code):
    data = load_results(folder)
    meta, check = data["metadata"], data["check"]
    if (code not in (0, 99) or meta["exit_code"] != code or not meta["collection_valid"] or not check["valid"]
            or meta["errors"] or not meta.get("recovery", {}).get("successful")
            or not meta.get("gateway_check", {}).get("complete")):
        raise ValueError("invalid preparation or cleanup: " + "; ".join(meta["errors"] + check["errors"]))
    if check != json.loads((folder / "collection-check.json").read_text(encoding="utf-8")):
        raise ValueError("collection replay differs from saved check")
    warnings = (set(meta["warnings"]) | set(check["warnings"])) - {BOUNDARY_WARNING}
    if warnings:
        raise ValueError(f"unexpected collection warnings: {sorted(warnings)}")
    for name, digest in meta["source_sha256"].items():
        if any(hashlib.sha256(p.read_bytes()).hexdigest() != digest
               for p in (folder / "inputs" / name, ROOT / "bench" / name)):
            raise ValueError(f"source changed: {name}")
    for name, digest in meta["custom_bundle"]["sha256"].items():
        if hashlib.sha256((folder / "inputs/custom-stack" / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"archived configuration changed: {name}")
    assessed = assessment(data)
    if (not assessed["data_valid"] or not assessed["duration_complete"]
            or assessed["dropped"] != 0 or assessed["unfinished"] != 0 or assessed["overall"] not in ("pass", "fail")):
        raise ValueError("preparation has incomplete or unassessable workload evidence")
    from custom_metric_run import replay
    return {"qualification": qualify(data), "assessment": assessed, "phases": phase_results(data),
            "custom_metric_check": replay(folder, data)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Without this flag, validate arguments only")
    args = parser.parse_args(argv)
    folder = args.output_dir.resolve()
    for target in (1, 2):
        parse_arguments(arguments(folder / f"target-{target}", target, "http://127.0.0.1:1"))
    if not args.execute:
        print("Validated two preparation bursts: target 1 then 2. No runtime or files changed.")
        return 0
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {"status": "starting", "protocol": "active-requests-preparation-v1", "pid": os.getpid(),
                "started_at": now(), "targets": [1, 2], "completed": [], "current": None,
                "comparison_started": False, "errors": []}
    save(folder / "manifest.json", manifest)
    try:
        save(folder / "host-before.json", host_snapshot())
        common = None
        with gateway_url(folder) as url:
            for target in (1, 2):
                run = folder / f"target-{target}"
                manifest.update(status="running", current=run.name)
                save(folder / "manifest.json", manifest)
                code = run_command([sys.executable, "-B", str(ROOT / "bench/run_pilot.py"),
                                    *arguments(run, target, url)], run)
                result = review(run, code)
                meta = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
                preflight = json.loads((run / "custom-preflight.json").read_text(encoding="utf-8"))
                frozen = {"sources": meta["source_sha256"], "stack": meta["custom_bundle"]["sha256"],
                          "infrastructure": preflight["identity"], "image": meta["initial_identity"]["image_id"],
                          "models": sorted({m["digest"] for m in meta["runtime_context"]["models"].values()}),
                          "profile": meta["runtime_context"]["minikube_profile"]["Config"]}
                if common is not None and frozen != common:
                    raise ValueError("configuration, executable inputs or runtime changed between preparations")
                common = frozen
                save(folder / "frozen-inputs.json", common)
                output = folder / f"target-{target}-analysis"
                if analyze([str(run), "--output-dir", str(output)]):
                    raise RuntimeError("offline analysis failed")
                save(output / "preparation.json", result)
                manifest["completed"].append({"target": target, "run": run.name, **result})
                save(folder / "manifest.json", manifest)
        selected = select(manifest["completed"])
        manifest.update(status="finished" if selected is not None else "inconclusive", selected_target=selected)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        manifest.update(status="stopped", errors=[str(error)])
        print(f"Preparation stopped: {error}", flush=True)
        return 1
    finally:
        manifest["finished_at"] = now()
        save(folder / "manifest.json", manifest)


if __name__ == "__main__":
    raise SystemExit(main())

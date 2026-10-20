"""Collect a fixed-one pilot or preliminary fixed-three check in a new results directory."""

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from observe import Observer, positive_number
from pilot_records import pilot_identity, reconcile


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def duration_seconds(value):
    parts = re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h)", value)
    if not parts or "".join(number + unit for number, unit in parts) != value:
        raise argparse.ArgumentTypeError("use a positive duration such as 30s, 2m or 1m30s")
    seconds = sum(float(number) * {"ms": .001, "s": 1, "m": 60, "h": 3600}[unit] for number, unit in parts)
    return positive_number(seconds)


def nonnegative_seconds(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be a finite nonnegative number")
    return number


def load_environment(args, run_id):
    # CLI/config environment overrides must not silently change or export a local experiment.
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith("K6_") and key not in
                   {"BASE_URL", "PROFILE", "RATE", "LOW_RATE", "DURATION", "SLO_MS", "RUN_ID", "REQUEST_EVENTS"}}
    environment.update(BASE_URL=args.base_url, PROFILE="steady", RATE=str(args.rate),
                       DURATION=args.duration, RUN_ID=run_id, REQUEST_EVENTS="1")
    return environment


class Collection:
    """One observer thread, reused for initial/periodic/final samples and counter continuity."""

    def __init__(self, observer, folder, interval, deployment, container, replicas=1):
        self.observer, self.folder, self.interval = observer, folder, interval
        self.deployment, self.container, self.replicas = deployment, container, replicas
        self.stop_event = threading.Event()
        self.failed = threading.Event()
        self.errors = []
        self.identity = None
        self.last = None
        self.thread = None
        self.output = None

    def collect(self):
        sample = self.observer.collect(self.interval)
        self.output.write(json.dumps(sample, ensure_ascii=False, allow_nan=False) + "\n")
        self.output.flush()
        self.last = sample
        identity = pilot_identity(sample, self.deployment, self.container, self.replicas)
        if self.identity is None:
            self.identity = identity
        elif identity != self.identity:
            raise ValueError("pilot container identity or restart count changed")
        return sample

    def start(self):
        self.output = (self.folder / "cluster.jsonl").open("x", encoding="utf-8")
        try:
            sample = self.collect()
            save_json(self.folder / "cluster-before.json", sample)
        except BaseException as error:
            self.errors.append(str(error))
            self.failed.set()
            if self.last is not None:
                save_json(self.folder / "cluster-before.json", self.last)
            raise
        self.thread = threading.Thread(target=self._run, name="pilot-observer", daemon=True)
        self.thread.start()

    def _run(self):
        try:
            # The first sample was already saved by start(); keep the same target cadence.
            pause = max(0, self.interval - self.last["collection_duration_seconds"])
            while not self.stop_event.wait(pause):
                before = time.monotonic()
                self.collect()
                pause = max(0, self.interval - (time.monotonic() - before))
        except Exception as error:
            self.errors.append(str(error))
            self.failed.set()

    def wait(self, seconds):
        if self.failed.wait(seconds):
            raise RuntimeError("cluster observation failed: " + "; ".join(self.errors))

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join()
        if self.output is not None:
            try:
                if self.thread is not None:
                    self.collect()
            except Exception as error:
                self.errors.append(str(error))
                self.failed.set()
            finally:
                self.output.close()
            if self.last is not None:
                save_json(self.folder / "cluster-after.json", self.last)


def warmup(base_url, workload, timeout, sender=None):
    record = {"phase": "warmup", "started_at_utc": utc_now(), "finished_at_utc": None,
              "timeout_seconds": timeout, "http_status": None, "successful": False,
              "output_tokens": None, "model_load_ms": None}
    started = time.monotonic()
    request = urllib.request.Request(base_url + "/api/generate", data=json.dumps(workload["request"]).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        if sender is None:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
                record["http_status"] = response.status
                body = json.load(response)
        else:
            record["http_status"], body = sender(request, timeout)
        record["successful"] = (record["http_status"] == 200 and isinstance(body, dict)
                                 and body.get("done") is True and isinstance(body.get("response"), str)
                                 and bool(body["response"].strip()))
        if not record["successful"]:
            raise ValueError("warmup did not produce a completed nonempty response")
        for source, target, divisor in (("eval_count", "output_tokens", 1), ("load_duration", "model_load_ms", 1e6)):
            value = body.get(source)
            if type(value) is int and 0 <= value <= 2**53 - 1:
                record[target] = value / divisor
    except (OSError, ValueError, urllib.error.URLError, subprocess.SubprocessError) as error:
        if isinstance(error, urllib.error.HTTPError):
            record["http_status"] = error.code
        record["error"] = str(error)
    finally:
        record["finished_at_utc"] = utc_now()
        record["duration_ms"] = (time.monotonic() - started) * 1000
    return record


def versions(k6, observer, environment):
    commands = {"k6": [k6, "version"], "kubectl": ["kubectl", "--context", observer.context, "version", "-o", "json"],
                "minikube": ["minikube", "version", "--output=json"],
                "docker": ["docker", "version", "--format", "{{json .}}"]}
    result = {"python": {"value": sys.version}, "platform": {"value": platform.platform()}}
    for name, command in commands.items():
        try:
            completed = subprocess.run(command, env=environment, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=15, check=False)
            result[name] = {"exit_code": completed.returncode, "stdout": completed.stdout.strip(),
                            "stderr": completed.stderr.strip()}
        except (OSError, subprocess.TimeoutExpired) as error:
            result[name] = {"error": str(error)}
    return result


def run_load(command, environment, folder, collection, metadata):
    with (folder / "console.txt").open("xb") as console:
        process = subprocess.Popen(command, env=environment, stdout=console, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
        try:
            deadline = time.monotonic() + metadata["duration_seconds"] + metadata["workload"]["graceful_stop_seconds"] + 60
            while process.poll() is None:
                collection.wait(.1)
                if time.monotonic() > deadline:
                    raise RuntimeError("k6 exceeded its duration, graceful stop and 60-second startup/export allowance")
            return process.returncode
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            metadata["k6_exit_code"] = process.returncode
            metadata["load_process_finished_at_utc"] = utc_now()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--rate", type=int, required=True, help="Requests per 10 seconds")
    parser.add_argument("--duration", default="2m")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--replicas", type=int, choices=(1, 3), default=1)
    parser.add_argument("--service", default="ollama")
    parser.add_argument("--context", default="ai-lab")
    parser.add_argument("--namespace", default="inference")
    parser.add_argument("--selector", default="app=ollama")
    parser.add_argument("--deployment", default="ollama")
    parser.add_argument("--container", default="ollama")
    parser.add_argument("--observer-interval", type=positive_number, default=5)
    parser.add_argument("--idle-seconds", type=nonnegative_seconds, default=60)
    parser.add_argument("--post-seconds", type=nonnegative_seconds, default=10)
    parser.add_argument("--warmup-timeout", type=positive_number, default=120)
    parser.add_argument("--activity-note", default="Not recorded", help="Other heavy activity on this computer")
    args = parser.parse_args(argv)
    if args.rate <= 0:
        parser.error("--rate must be positive")
    try:
        seconds = duration_seconds(args.duration)
    except argparse.ArgumentTypeError as error:
        parser.error(str(error))
    url = urllib.parse.urlsplit(args.base_url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        parser.error("--base-url must be an HTTP(S) URL without credentials, query or fragment")
    args.base_url = args.base_url.rstrip("/")
    args.run_dir = args.run_dir.resolve()
    try:
        args.run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"Refusing to overwrite existing run path: {args.run_dir}", file=sys.stderr)
        return 2

    source = Path(__file__).resolve().parent
    metadata = {"schema_version": 2, "run_id": uuid.uuid4().hex, "status": "starting", "phase": "preflight",
                "started_at_utc": utc_now(), "finished_at_utc": None, "base_url": args.base_url,
                "profile": "steady", "rate": args.rate, "time_unit": "10s", "duration": args.duration,
                "duration_seconds": seconds, "context": args.context, "namespace": args.namespace,
                "selector": args.selector, "deployment": args.deployment, "container": args.container,
                "observer_interval_seconds": args.observer_interval, "idle_seconds": args.idle_seconds,
                "post_seconds": args.post_seconds, "warmup_timeout_seconds": args.warmup_timeout,
                "activity_note": args.activity_note, "k6_exit_code": None, "collector_exit_code": None,
                "collection_valid": False, "server_drain_verified": False, "phases": [], "errors": [], "warnings": []}
    metadata.update(expected_replicas=args.replicas, mode=f"fixed-{args.replicas}",
                    purpose="pilot" if args.replicas == 1 else "preliminary-fixed-replica-check")
    metadata_path = args.run_dir / "metadata.json"
    collection = None
    exit_code = 1

    def phase(name):
        metadata["phase"] = name
        metadata["phases"].append({"phase": name, "started_at_utc": utc_now()})
        save_json(metadata_path, metadata)

    save_json(metadata_path, metadata)
    try:
        # Preserve the exact executable inputs with each run, as well as their hashes.
        inputs = args.run_dir / "inputs"
        inputs.mkdir()
        metadata["source_sha256"] = {}
        names = ["inference.js", "workload.json", "run_pilot.py", "observe.py", "pilot_records.py"]
        if args.replicas == 3:
            names.append("fixed_replicas.py")
        for name in names:
            shutil.copyfile(source / name, inputs / name)
            metadata["source_sha256"][name] = hashlib.sha256((inputs / name).read_bytes()).hexdigest()
        metadata["script_sha256"] = metadata["source_sha256"]["inference.js"].upper()
        workload = json.loads((inputs / "workload.json").read_text(encoding="utf-8"))
        metadata["workload"] = workload
        k6 = shutil.which("k6")
        if k6 is None:
            raise FileNotFoundError("k6 is not available on PATH")
        environment = load_environment(args, metadata["run_id"])
        observer = Observer(args.context, args.namespace, args.selector)
        metadata["versions"] = versions(k6, observer, environment)
        for name in ("k6", "kubectl", "minikube", "docker"):
            if metadata["versions"].get(name, {}).get("exit_code") != 0:
                metadata["warnings"].append(f"cannot record {name} version; see versions diagnostics")
        metadata["k6_version"] = metadata["versions"].get("k6", {}).get("stdout")
        # An explicit empty config prevents a user's k6 config file overriding the scenario.
        save_json(inputs / "k6-config.json", {})
        collection = Collection(observer, args.run_dir, args.observer_interval, args.deployment, args.container, args.replicas)
        collection.start()
        metadata["initial_identity"] = collection.identity
        metadata["deployment_snapshot"] = next(d for d in collection.last["deployments"]["items"]
                                                if d["metadata"]["name"] == args.deployment)
        pods = collection.last["pods"]["items"]
        metadata["pod_snapshot"] = pods[0]
        if args.replicas == 3:
            from fixed_replicas import capture_route, check_route
            metadata["pod_snapshots"] = pods
            route = capture_route(observer, args.service)
            save_json(args.run_dir / "service-route.json", route)
            check_route(route, collection.identity, metadata["deployment_snapshot"])
        phase("idle")
        collection.wait(args.idle_seconds)
        phase("warmup")
        if args.replicas == 3:
            from fixed_replicas import warmup_pods
            record = warmup_pods(observer, pods, workload, args.warmup_timeout, warmup)
        else:
            record = warmup(args.base_url, workload, args.warmup_timeout)
        save_json(args.run_dir / "warmup.json", record)
        if not record["successful"]:
            raise RuntimeError("warmup failed; see warmup.json")
        collection.wait(0)
        phase("load")
        command = [k6, "run", "--config", str(inputs / "k6-config.json"), "--no-usage-report", "--no-color",
                   "--log-format", "raw", "--console-output", str(args.run_dir / "request-events.jsonl"),
                   "--out", f"json={args.run_dir / 'requests.json'}",
                   "--summary-export", str(args.run_dir / "summary.json"), str(inputs / "inference.js")]
        metadata["k6_command"] = command
        metadata["load_process_started_at_utc"] = utc_now()
        save_json(metadata_path, metadata)
        result = run_load(command, environment, args.run_dir, collection, metadata)
        if result not in (0, 99):
            raise RuntimeError(f"k6 failed with exit code {result}")
        phase("post_load")
        collection.wait(args.post_seconds)
        if args.replicas == 3:
            from fixed_replicas import capture_logs
            capture_logs(observer, pods, args.container, args.run_dir, metadata["load_process_started_at_utc"])
        exit_code = result
    except KeyboardInterrupt:
        metadata["errors"].append("interrupted by user; pending server work must be checked before another probe")
        exit_code = 130
    except (OSError, ValueError, RuntimeError, KeyError, StopIteration, subprocess.SubprocessError) as error:
        metadata["errors"].append(str(error))
        print(str(error), file=sys.stderr)
        exit_code = 1
    finally:
        if collection is not None:
            try:
                collection.stop()
            except OSError as error:
                collection.errors.append(f"cannot finish observation files: {error}")
                collection.failed.set()
            metadata["collector_exit_code"] = 1 if collection.failed.is_set() else 0
            metadata["errors"].extend(collection.errors)
        phase("validation")
        report = reconcile(args.run_dir, metadata)
        save_json(args.run_dir / "collection-check.json", report)
        metadata["counts"] = report["counts"]
        metadata["load_window"] = report["load_window"]
        metadata["warnings"] = report["warnings"]
        metadata["collection_valid"] = report["valid"] and not metadata["errors"]
        if not metadata["collection_valid"] and exit_code in (0, 99):
            exit_code = 1
        metadata["status"] = ("finished" if metadata["collection_valid"] and exit_code == 0 else
                              "thresholds_failed" if metadata["collection_valid"] and exit_code == 99 else
                              "interrupted" if exit_code == 130 else "failed")
        metadata["exit_code"] = exit_code
        metadata["finished_at_utc"] = utc_now()
        save_json(metadata_path, metadata)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

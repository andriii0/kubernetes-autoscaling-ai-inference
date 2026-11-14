"""Collect fixed-replica or preliminary autoscaling evidence in a new results directory."""

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
from records import pilot_identity
from pilot_records import reconcile


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
                   {"BASE_URL", "PROFILE", "RATE", "LOW_RATE", "DURATION", "SLO_MS", "RUN_ID", "REQUEST_EVENTS", "MAIN_PROTOCOL",
                    "GATEWAY_REQUEST_IDS"}}
    environment.update(BASE_URL=args.base_url, PROFILE=getattr(args, "profile", "steady"), RATE=str(args.rate),
                       LOW_RATE=str(getattr(args, "low_rate", 2)),
                       DURATION=args.duration, RUN_ID=run_id, REQUEST_EVENTS="1", K6_AUTO_EXTENSION_RESOLUTION="false")
    if getattr(args, 'protocol_version', None):
        environment['MAIN_PROTOCOL'] = args.protocol_version
    if getattr(args, 'custom_metric_policy', None):
        environment['GATEWAY_REQUEST_IDS'] = '1'
    if args.slo_ms is not None:
        environment['SLO_MS'] = str(args.slo_ms)
    return environment


class Collection:
    """One observer thread, reused for initial/periodic/final samples and counter continuity."""

    def __init__(self, observer, folder, interval, deployment, container, replicas=1, session=None, main=False):
        self.session = session
        self.main = main
        self.lock = threading.RLock()
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
        with self.lock:
            sample = self.observer.collect(self.interval)
            self.output.write(json.dumps(sample, ensure_ascii=False, allow_nan=False) + "\n")
            self.output.flush()
            self.last = sample
            if self.main and not self.session:
                spec = next(d['spec'] for d in sample['deployments']['items'] if d['metadata']['name'] == self.deployment)
                if hasattr(self, 'deployment_spec') and self.deployment_spec != spec:
                    raise ValueError('Deployment configuration changed during collection')
                self.deployment_spec = spec
            if self.session:
                self.session.accept(sample)
                if self.identity is None:
                    self.identity = pilot_identity(sample, self.deployment, self.container)
            else:
                identity = pilot_identity(sample, self.deployment, self.container, self.replicas, allow_resource_gaps=self.main)
                if self.identity is None:
                    self.identity = identity
                elif identity != self.identity:
                    raise ValueError("pilot container identity or restart count changed")
            if getattr(self, 'fixed_logs', None):
                self.fixed_logs.update(sample)
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
            from run_lock import register_process
            register_process(process)
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


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol-version", choices=("1.1",))
    parser.add_argument("--repetition", type=int, choices=(1, 2, 3))
    parser.add_argument("--planned-order", type=int)
    parser.add_argument("--actual-order", type=int, help="Attempt number, including failed/replaced attempts")
    parser.add_argument("--replaces-run", help="Path or run ID of an earlier attempt; never overwrite it")
    parser.add_argument("--replacement-reason")
    parser.add_argument("--diagnostic-warmup-wait", choices=("immediate", "quiet"),
                        help="Fixed-one steady diagnostic; vary only post-warmup settling, outside the main protocol")
    parser.add_argument("--pilot-preparation", action="store_true",
                        help="Use recovery and quiet-state gates for fixed-mode or autoscaling burst checks")
    parser.add_argument("--custom-metric-policy", choices=("cpu", "active-1", "active-2"),
                        help="Separate prepared extension through the installed inference gateway")
    parser.add_argument("--custom-metric-comparison", action="store_true",
                        help="Label the separately authorized comparison; retains all extension checks")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--rate", type=int, required=True, help="Requests per 10 seconds")
    parser.add_argument("--duration")
    parser.add_argument("--slo-ms", type=positive_number,
                        help="Optional p95 successful-response latency threshold in milliseconds")
    parser.add_argument("--mode", choices=("autoscaling", "fixed-1", "fixed-3"))
    parser.add_argument("--profile", choices=("steady", "burst"), default="steady")
    parser.add_argument("--low-rate", type=int, default=2)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--replicas", type=int, choices=(1, 3))
    parser.add_argument("--service", default="ollama")
    parser.add_argument("--context", default="ai-lab")
    parser.add_argument("--namespace", default="inference")
    parser.add_argument("--selector", default="app=ollama")
    parser.add_argument("--deployment", default="ollama")
    parser.add_argument("--container", default="ollama")
    parser.add_argument("--observer-interval", type=positive_number, default=5)
    parser.add_argument("--idle-seconds", type=nonnegative_seconds, default=60)
    parser.add_argument("--post-seconds", type=nonnegative_seconds)
    parser.add_argument("--warmup-timeout", type=positive_number, default=120)
    parser.add_argument("--activity-note", default="Not recorded", help="Other heavy activity on this computer")
    args = parser.parse_args(argv)
    if args.custom_metric_comparison and args.custom_metric_policy not in ("cpu", "active-1"):
        parser.error("comparison requires cpu or the selected active-1 policy")
    if args.rate <= 0 or args.low_rate <= 0:
        parser.error("rates must be positive")
    if args.mode == "autoscaling" and args.replicas is not None:
        parser.error("autoscaling requires no --replicas")
    if args.mode and args.mode.startswith("fixed-") and args.replicas is not None and args.mode != f"fixed-{args.replicas}":
        parser.error("--mode conflicts with --replicas")
    if args.profile == "burst" and args.duration is not None:
        parser.error("burst duration is defined by workload stages; omit --duration")
    args.mode = args.mode or f"fixed-{args.replicas or 1}"
    args.replicas = int(args.mode[-1]) if args.mode.startswith("fixed-") else 1
    if args.diagnostic_warmup_wait and (args.protocol_version or args.mode != "fixed-1" or args.profile != "steady"):
        parser.error("--diagnostic-warmup-wait requires fixed-1/steady without --protocol-version")
    pilot_mode = args.mode != "autoscaling" or args.profile == "burst"
    if args.pilot_preparation and (args.protocol_version or args.diagnostic_warmup_wait or not pilot_mode):
        parser.error("--pilot-preparation requires a fixed mode or autoscaling/burst without protocol or diagnostic options")
    prepared = bool(args.protocol_version or args.diagnostic_warmup_wait or args.pilot_preparation)
    args.post_seconds = args.post_seconds if args.post_seconds is not None else (300 if args.mode == "autoscaling" else 10)
    if args.custom_metric_policy and (
            not args.pilot_preparation or args.mode != "autoscaling" or args.profile != "burst"
            or args.rate != 12 or args.low_rate != 2 or args.post_seconds != 300
            or args.observer_interval != 5 or args.idle_seconds != 60
            or args.slo_ms != 5000 or args.protocol_version or args.diagnostic_warmup_wait
            or (args.context, args.namespace, args.deployment, args.service, args.selector, args.container)
            != ("ai-lab", "inference", "ollama", "ollama", "app=ollama", "ollama")):
        parser.error("custom-metric policy requires the separate prepared ai-lab autoscaling burst: 2/12, 5s observer, 60s idle, 300s post, 5000ms target")
    workload = json.loads((Path(__file__).parent / "workload.json").read_text(encoding="utf-8"))
    stages = workload["burst_stages"]
    if args.profile == "burst":
        args.duration = f"{sum(s['seconds'] for s in stages)}s"
    else:
        args.duration = args.duration or (f"{workload['main_protocol']['steady_seconds']}s" if args.protocol_version else "2m")
    try:
        seconds = duration_seconds(args.duration)
        if args.protocol_version or any(v is not None for v in (args.repetition, args.planned_order, args.actual_order, args.replaces_run)):
            from main_protocol import validate_arguments
            validate_arguments(args, workload, seconds)
        if bool(args.replaces_run) != bool(args.replacement_reason):
            raise ValueError("provide both --replaces-run and --replacement-reason")
    except (argparse.ArgumentTypeError, ValueError) as error:
        parser.error(str(error))
    url = urllib.parse.urlsplit(args.base_url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        parser.error("--base-url must be an HTTP(S) URL without credentials, query or fragment")
    args.base_url = args.base_url.rstrip("/")
    args.run_dir = args.run_dir.resolve()
    return args, workload, seconds, prepared


def create_metadata(args, workload, seconds):
    metadata = {"schema_version": 2, "source_archive_version": 2, "run_id": uuid.uuid4().hex, "status": "starting", "phase": "preflight",
                "started_at_utc": utc_now(), "finished_at_utc": None, "base_url": args.base_url,
                "profile": args.profile, "low_rate": args.low_rate, "burst_stages": workload["burst_stages"] if args.profile == "burst" else None, "rate": args.rate, "time_unit": "10s", "duration": args.duration,
                "duration_seconds": seconds, "slo_ms": args.slo_ms, "context": args.context, "namespace": args.namespace,
                "selector": args.selector, "deployment": args.deployment, "container": args.container,
                "observer_interval_seconds": args.observer_interval, "idle_seconds": args.idle_seconds,
                "post_seconds": args.post_seconds, "warmup_timeout_seconds": args.warmup_timeout,
                "activity_note": args.activity_note, "k6_exit_code": None, "collector_exit_code": None,
                "collection_valid": False, "server_drain_verified": False, "phases": [], "errors": [], "warnings": []}
    metadata.update(expected_replicas=None if args.mode == "autoscaling" else args.replicas, mode=args.mode,
                    purpose="preliminary-hpa-check" if args.mode == "autoscaling" else
                    "pilot" if args.replicas == 1 else "preliminary-fixed-replica-check")
    if args.diagnostic_warmup_wait:
        metadata.update(purpose="diagnostic-warmup-wait", diagnostic_warmup_wait=args.diagnostic_warmup_wait)
    if args.pilot_preparation:
        metadata.update(purpose="preliminary-hpa-check" if args.mode == "autoscaling" else
                        "pilot-recalibration" if args.replicas == 1 else "preliminary-fixed-replica-check",
                        pilot_preparation=True)
    if args.protocol_version:
        metadata.update(purpose="main-series", workload=workload, protocol_version=args.protocol_version, repetition=args.repetition,
                        planned_order=args.planned_order, actual_order=args.actual_order,
                        replaces_run=args.replaces_run, replacement_reason=args.replacement_reason)
    if args.custom_metric_policy:
        metadata.update(purpose="custom-metric-preparation", custom_metric_policy=args.custom_metric_policy,
                        extension_version="active-requests-preparation-v2")
    if args.custom_metric_comparison:
        metadata.update(purpose="custom-metric-comparison", extension_version="active-requests-comparison-v3")
    metadata["latency_clock"] = "monotonic-v1"
    return metadata


def archive_inputs(args, metadata, prepared):
    source = Path(__file__).resolve().parent
    # Preserve the exact executable inputs with each run, as well as their hashes.
    inputs = args.run_dir / "inputs"
    inputs.mkdir()
    metadata["source_sha256"] = {}
    names = ["inference.js", "workload.json", "run_pilot.py", "observe.py", "pilot_records.py", "records.py", "run_lock.py", "build_k6.py"]
    if prepared:
        names.extend(["main_protocol.py", "analyze.py"])
        from main_protocol import source_revision
        metadata["source_revision"] = source_revision(source.parent)
    if prepared or args.replicas == 3 or args.mode == "autoscaling":
        names.append("fixed_replicas.py")
    if args.mode == "autoscaling":
        names.append("autoscaling.py")
    if args.custom_metric_policy:
        names.extend(["custom_metric_stack.py", "custom_metrics.py", "check_custom_metric.py",
                      "custom_metric_run.py", "prepare_custom_metric.py", "runtime.py"])
    if args.custom_metric_comparison:
        names.extend(["run_custom_comparison.py", "analyze_custom_comparison.py"])
    for name in names:
        shutil.copyfile(source / name, inputs / name)
        metadata["source_sha256"][name] = hashlib.sha256((inputs / name).read_bytes()).hexdigest()
    metadata["script_sha256"] = metadata["source_sha256"]["inference.js"].upper()
    workload = json.loads((inputs / "workload.json").read_text(encoding="utf-8"))
    metadata["workload"] = workload
    return inputs, workload


def prepare_collection(args, metadata, collection, workload, prepared, phase):
    observer, session = collection.observer, collection.session
    collection.start()
    metadata["initial_identity"] = collection.identity
    metadata["deployment_snapshot"] = next(d for d in collection.last["deployments"]["items"]
                                            if d["metadata"]["name"] == args.deployment)
    if prepared:
        from main_protocol import check_configuration
        check_configuration(metadata["deployment_snapshot"])
    pods = collection.last["pods"]["items"]
    metadata["pod_snapshot"] = pods[0]
    if prepared:
        from main_protocol import runtime_context
        metadata["runtime_context"] = runtime_context(observer, pods, args.run_dir, workload["request"]["model"])
    if args.replicas == 3 or prepared and not session:
        from fixed_replicas import capture_route, check_route
        metadata["pod_snapshots"] = pods
        route = capture_route(observer, args.service)
        save_json(args.run_dir / "service-route.json", route)
        initial = collection.identity if isinstance(collection.identity, list) else [collection.identity]
        check_route(route, initial, metadata["deployment_snapshot"])
    if prepared:
        from main_protocol import settle
        phase("initial_quiet")
        metadata["initial_quiet"] = settle(collection, metadata["phases"][-1]["started_at_utc"])
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
    if args.protocol_version or args.diagnostic_warmup_wait == "quiet" or args.pilot_preparation:
        phase("post_warmup_quiet")
        metadata["post_warmup_quiet"] = settle(collection, metadata["phases"][-1]["started_at_utc"], bool(session))
    if session:
        phase("hpa_readiness")
        session.enable(collection)
        metadata["hpa_spec"] = session.state.hpa_spec
        metadata["hpa_applied_at_utc"] = session.applied_at_utc
        save_json(args.run_dir / "metadata.json", metadata)
    return pods


def execute_load(args, metadata, collection, inputs, k6, environment, pods, prepared, phase):
    observer, session = collection.observer, collection.session
    phase("load")
    command = [k6, "run", "--config", str(inputs / "k6-config.json"), "--no-usage-report", "--no-color",
               "--log-format", "raw", "--console-output", str(args.run_dir / "request-events.jsonl"),
               "--out", f"json={args.run_dir / 'requests.json'}",
               "--summary-export", str(args.run_dir / "summary.json"), str(inputs / "inference.js")]
    metadata["k6_command"] = command
    metadata["load_process_started_at_utc"] = utc_now()
    if (args.replicas == 3 or prepared) and not session:
        from autoscaling import Logs
        with collection.lock:
            collection.fixed_logs = Logs(observer, args.run_dir, args.container)
            collection.fixed_logs.update(collection.last)
    save_json(args.run_dir / "metadata.json", metadata)
    result = run_load(command, environment, args.run_dir, collection, metadata)
    if result not in (0, 99):
        raise RuntimeError(f"k6 failed with exit code {result}")
    if prepared:
        from main_protocol import finish_scheduled_window
        finish_scheduled_window(collection, args.run_dir, metadata)
    phase("post_load_no_new_requests" if session else "post_load")
    collection.wait(args.post_seconds)
    if (args.replicas == 3 or prepared and not session) and not getattr(collection, 'fixed_logs', None):
        from fixed_replicas import capture_logs
        capture_logs(observer, pods, args.container, args.run_dir, metadata["load_process_started_at_utc"])
    return result


def finalize_run(args, metadata, collection, session, pods, prepared, phase, exit_code):
    if session and session.state and session.state.hpa_spec:
        metadata["hpa_spec"] = session.state.hpa_spec
        metadata["hpa_applied_at_utc"] = session.applied_at_utc
    if collection is not None:
        try:
            collection.stop()
        except OSError as error:
            collection.errors.append(f"cannot finish observation files: {error}")
            collection.failed.set()
        metadata["collector_exit_code"] = 1 if collection.failed.is_set() else 0
        metadata["errors"].extend(collection.errors)
    if session:
        try:
            if session.logs:
                session.logs.stop()
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            metadata["errors"].append(f"log shutdown: {error}")
        metadata["recovery"] = session.restore()
        if getattr(args, "custom_metric_policy", None):
            if not metadata["recovery"].get("successful"):
                metadata["errors"].append("custom-metric cleanup failed; see recovery.json")
            try:
                metadata["gateway_check"] = session.verify_gateway()
            except (OSError, ValueError, RuntimeError, KeyError) as error:
                metadata["errors"].append(f"gateway validation: {error}")
    if collection is not None and getattr(collection, 'fixed_logs', None):
        try:
            collection.fixed_logs.stop()
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            metadata["errors"].append(f"fixed-mode log shutdown: {error}")
    if prepared and not session and metadata.get("load_process_started_at_utc") and not (args.run_dir / "pod-logs").exists():
        try:
            from fixed_replicas import capture_logs
            capture_logs(collection.observer, pods, args.container, args.run_dir, metadata["load_process_started_at_utc"])
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            metadata["errors"].append(f"final fixed-mode logs: {error}")
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
    metadata["phases"][-1]["finished_at_utc"] = metadata["finished_at_utc"]
    if args.protocol_version:
        from analyze import save_assessment
        metadata["assessment"] = save_assessment(args.run_dir, metadata, report)
    save_json(args.run_dir / "metadata.json", metadata)
    return exit_code


from run_lock import exclusive_main


@exclusive_main
def main(argv=None):
    args, workload, seconds, prepared = parse_arguments(argv)
    try:
        args.run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"Refusing to overwrite existing run path: {args.run_dir}", file=sys.stderr)
        return 2

    metadata = create_metadata(args, workload, seconds)
    metadata_path = args.run_dir / "metadata.json"
    collection = None
    session = None
    exit_code = 1
    pods = []

    def phase(name):
        if metadata["phases"]:
            metadata["phases"][-1]["finished_at_utc"] = utc_now()
        metadata["phase"] = name
        metadata["phases"].append({"phase": name, "started_at_utc": utc_now()})
        save_json(metadata_path, metadata)

    save_json(metadata_path, metadata)
    try:
        inputs, workload = archive_inputs(args, metadata, prepared)
        from build_k6 import MODULE, runtime
        k6, metadata["timing_runtime"] = runtime()
        timer_sources = inputs / "monotonic"
        timer_sources.mkdir()
        for name in metadata["timing_runtime"]["sources"]:
            shutil.copyfile(MODULE / name, timer_sources / name)
        environment = load_environment(args, metadata["run_id"])
        observer = Observer(args.context, args.namespace, args.selector)
        metadata["versions"] = versions(k6, observer, environment)
        for name in ("k6", "kubectl", "minikube", "docker"):
            if metadata["versions"].get(name, {}).get("exit_code") != 0:
                metadata["warnings"].append(f"cannot record {name} version; see versions diagnostics")
        metadata["k6_version"] = metadata["versions"].get("k6", {}).get("stdout")
        # An explicit empty config prevents a user's k6 config file overriding the scenario.
        save_json(inputs / "k6-config.json", {})
        if prepared:
            from main_protocol import recover
            phase("recovery_quiet")
            metadata["initial_recovery"] = recover(observer, args.run_dir, args.container)
        if args.mode == "autoscaling":
            from autoscaling import Session
            if args.custom_metric_policy:
                from custom_metric_run import CustomSession as Session
                from custom_metric_stack import render
                render(inputs / "custom-stack")
                manifest = inputs / "custom-stack" / f"hpa-{args.custom_metric_policy}.json"
                metadata["custom_bundle"] = json.loads((inputs / "custom-stack" / "bundle.json").read_text(encoding="utf-8"))
            else:
                manifest = inputs / "hpa.yaml"
                shutil.copyfile(Path(__file__).resolve().parent.parent / "deploy/hpa.yaml", manifest)
                metadata["source_sha256"]["hpa.yaml"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
            session = Session(observer, args.run_dir, args.deployment, args.container, args.service, manifest)
            phase("reset")
            session.prepare()
        elif prepared:
            from main_protocol import prepare_fixed
            phase("initial_state")
            prepare_fixed(observer, args.deployment, args.container, args.replicas)
        collection = Collection(observer, args.run_dir, args.observer_interval, args.deployment, args.container,
                                args.replicas, session=session, main=bool(args.protocol_version))
        pods = prepare_collection(args, metadata, collection, workload, prepared, phase)
        exit_code = execute_load(args, metadata, collection, inputs, k6, environment, pods, prepared, phase)
    except KeyboardInterrupt:
        metadata["errors"].append("interrupted by user; pending server work must be checked before another probe")
        exit_code = 130
    except (OSError, ValueError, RuntimeError, KeyError, StopIteration, subprocess.SubprocessError) as error:
        metadata["errors"].append(str(error))
        print(str(error), file=sys.stderr)
        exit_code = 1
    finally:
        exit_code = finalize_run(args, metadata, collection, session, pods, prepared, phase, exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

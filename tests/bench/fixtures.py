"""Shared Kubernetes samples and temporary run evidence for bench tests."""

import copy
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request

import autoscaling
import fixed_replicas
import pilot_records
import records
import run_pilot

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / 'bench'


def sample(at="2026-10-18T12:00:00Z"):
    return {"time": at, "collection_duration_seconds": 0, "errors": [],
            "pods": {"items": [{"metadata": {"name": "ollama-one", "namespace": "inference", "uid": "pod-1",
                                              "labels": {"app": "ollama"}},
                                "spec": {"nodeName": "ai-lab", "containers": [{"name": "ollama", "resources": {
                                    "requests": {"cpu": "2", "memory": "1Gi"}, "limits": {"cpu": "2", "memory": "2Gi"}}}]},
                                "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}],
                                           "containerStatuses": [{"name": "ollama", "ready": True, "restartCount": 0,
                                                                  "state": {"running": {}}, "containerID": "container-1",
                                                                  "imageID": "sha256:image-1"}]}}]},
            "deployments": {"items": [{"metadata": {"name": "ollama", "generation": 1},
                                       "spec": {"replicas": 1, "selector": {"matchLabels": {"app": "ollama"}}},
                                       "status": {"replicas": 1, "updatedReplicas": 1, "readyReplicas": 1,
                                                  "availableReplicas": 1, "observedGeneration": 1}}]},
            "hpa": {"items": []}, "nodes": {"items": []},
            "resource_usage": [{"scope": "container", "node": "ai-lab", "pod_uid": "pod-1", "container": "ollama",
                                "cpu_usage_seconds_total": 10, "memory_working_set_bytes": 1000},
                               {"scope": "node", "node": "ai-lab", "cpu_usage_seconds_total": 20,
                                "memory_working_set_bytes": 2000}]}

def write_lines(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def three_sample(at="2026-10-18T12:00:00Z"):
    result = sample(at)
    original = copy.deepcopy(result["pods"]["items"][0])
    resource = copy.deepcopy(result["resource_usage"][0])
    result["pods"]["items"] = []
    result["resource_usage"] = [result["resource_usage"][1]]
    for index in range(1, 4):
        pod = copy.deepcopy(original)
        pod["metadata"].update(name=f"ollama-{index}", uid=f"pod-{index}")
        pod["status"]["conditions"][0]["lastTransitionTime"] = "2026-10-18T11:59:00Z"
        pod["status"]["containerStatuses"][0]["containerID"] = f"container-{index}"
        result["pods"]["items"].append(pod)
        record = {**resource, "pod_uid": f"pod-{index}", "namespace": "inference",
                  "cpu_cores": index, "memory_working_set_bytes": index * 2**20,
                  "cpu_timestamp_ms": records.timestamp(at) * 1000,
                  "memory_timestamp_ms": records.timestamp(at) * 1000}
        result["resource_usage"].append(record)
    target = result["deployments"]["items"][0]
    target["spec"]["replicas"] = 3
    target["status"].update(replicas=3, readyReplicas=3, updatedReplicas=3, availableReplicas=3)
    return result

def route():
    return {"service": {"spec": {"selector": {"app": "ollama"}, "ports": [{"port": 11434, "targetPort": 11434}]}},
            "endpoint_slices": {"items": [{"endpoints": [
                {"conditions": {"ready": True}, "targetRef": {"kind": "Pod", "uid": f"pod-{i}"}}
                for i in range(1, 4)]}]}}


def hpa():
    return {'metadata': {'name': 'ollama'}, 'spec': {'scaleTargetRef': {'kind': 'Deployment', 'name': 'ollama'},
            'minReplicas': 1, 'maxReplicas': 3}, 'status': {'currentReplicas': 1, 'desiredReplicas': 1,
            'currentMetrics': [{'type': 'Resource', 'resource': {'name': 'cpu', 'current': {'averageUtilization': 2}}}],
            'conditions': [{'type': 'ScalingActive', 'status': 'True'}]}}


class RunFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.metadata = {"run_id": "test", "duration_seconds": 1, "observer_interval_seconds": 5,
                         "initial_identity": records.pilot_identity(sample()),
                         "deployment": "ollama", "container": "ollama", "errors": [], "k6_exit_code": 0,
                         "collector_exit_code": 0, "load_process_started_at_utc": "2026-10-18T12:00:01Z"}
        (self.folder / "inputs").mkdir()
        hashes = {}
        for name in ("inference.js", "workload.json", "run_pilot.py", "observe.py", "pilot_records.py"):
            data = name.encode()
            (self.folder / "inputs" / name).write_bytes(data)
            hashes[name] = hashlib.sha256(data).hexdigest()
        self.metadata["source_sha256"] = hashes
        (self.folder / "warmup.json").write_text(json.dumps({"phase": "warmup", "successful": True,
            "http_status": 200, "finished_at_utc": "2026-10-18T12:00:00.900Z"}))
        self.start = {"schema_version": 1, "run_id": "test", "phase": "load", "request_id": "test:load:0",
                      "scenario": "load", "iteration": 0, "vu": 1, "event": "started",
                      "scenario_started_at_utc": "2026-10-18T12:00:01Z", "started_at_utc": "2026-10-18T12:00:01Z"}
        self.completed = {**self.start, "event": "completed", "finished_at_utc": "2026-10-18T12:00:01.500Z",
                          "duration_ms": 500, "outcome": "success", "http_status": 200,
                          "error_category": None, "output_tokens": None, "model_load_ms": 0}
        self.events = [self.start, self.completed]
        counts = {"requests_started": 1, "requests_completed": 1, "http_reqs": 1, "iterations": 1, "dropped_iterations": 0}
        self.summary = {"metrics": {k: {"count": v} for k, v in counts.items()}}
        self.summary["metrics"]["inference_errors"] = {"passes": 0, "fails": 1}
        for name in ('request_latency_ms', 'successful_latency_ms'):
            self.summary['metrics'][name] = {'avg': 500, 'min': 500, 'max': 500, 'p(95)': 500}
        self.points = [{"type": "Point", "metric": k, "data": {"value": v}} for k, v in counts.items()]
        self.points.extend({'type': 'Point', 'metric': name, 'data': {'value': 500}}
                           for name in ('request_latency_ms', 'successful_latency_ms'))
        self.points.append({"type": "Point", "metric": "inference_errors", "data": {"value": 0}})
        self.samples = [sample(), sample("2026-10-18T12:00:05Z")]

    def remove_latency(self, *metrics):
        self.points = [p for p in self.points if p['metric'] not in metrics]
        for metric in metrics:
            self.summary['metrics'].pop(metric, None)

    def check(self):
        write_lines(self.folder / "request-events.jsonl", self.events)
        write_lines(self.folder / "requests.json", self.points)
        write_lines(self.folder / "cluster.jsonl", self.samples)
        (self.folder / "summary.json").write_text(json.dumps(self.summary))
        return pilot_records.reconcile(self.folder, self.metadata)


def autoscaling_fixture(owner):
    fixture = RunFixture()
    fixture.setUp()
    owner.addCleanup(fixture.doCleanups)
    fixture.metadata.update(mode='autoscaling', expected_replicas=None, namespace='inference',
                            deployment_snapshot=sample()['deployments']['items'][0], hpa_spec=hpa()['spec'], profile='steady')
    (fixture.folder / 'service-route.json').write_text(json.dumps({'service': {'spec': {'selector': {'app': 'ollama'},
        'ports': [{'port': 11434, 'targetPort': 11434}]}}, 'endpoint_slices': {'items': [{'endpoints': [
            {'conditions': {'ready': True}, 'targetRef': {'kind': 'Pod', 'uid': 'pod-1'}}]}]}}))
    (fixture.folder / 'pod-logs').mkdir()
    (fixture.folder / 'pod-logs/pod-1.log').write_text('')
    (fixture.folder / 'log-coverage.json').write_text(json.dumps({'pod-1': {'pod_name': 'ollama-one', 'complete': True,
        'exit_code': 1, 'stopped_by_collector': True}}))
    return fixture


class FakeObserver:
    broken = False

    def __init__(self, context, namespace, selector):
        self.context, self.namespace, self.selector = context, namespace, selector

    def collect(self, interval):
        result = sample(run_pilot.utc_now())
        if self.broken:
            result["errors"] = [{"source": "test", "message": "unavailable"}]
        return result


class PilotLauncherFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name) / "run"
        self.args = ["--base-url", "http://127.0.0.1:1234", "--rate", "2", "--run-dir", str(self.folder),
                     "--idle-seconds", "0", "--post-seconds", "0", "--duration", "1s"]
        FakeObserver.broken = False

    def metadata(self):
        return json.loads((self.folder / "metadata.json").read_text())

    def fake_versions(self, *args):
        return {name: {"stdout": "test-version", "exit_code": 0} for name in ("k6", "kubectl", "minikube", "docker")}

    def server(self, fail_after_warmup=False, fail_warmup=False):
        captured = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                status = 503 if fail_warmup or (fail_after_warmup and len(captured) > 1) else 200
                data = json.dumps({"done": True, "response": "Stub answer", "eval_count": 0, "load_duration": 0}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()

        def close():
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

        self.addCleanup(close)
        self.args[1] = f"http://127.0.0.1:{server.server_port}"
        return captured

    def invoke(self):
        with patch.object(run_pilot, "Observer", FakeObserver), patch.object(run_pilot, "versions", self.fake_versions), \
             patch.object(run_pilot.shutil, "which", return_value=shutil.which('k6') or 'test-k6'):
            return run_pilot.main(self.args)

    def assert_run_exit(self, expected):
        actual = self.invoke()
        if actual != expected:
            preserved = Path(tempfile.mkdtemp(prefix="pilot-test-failure-")) / "run"
            shutil.copytree(self.folder, preserved)
            diagnostics = {name: (self.folder / name).read_text(encoding="utf-8")
                           for name in ("collection-check.json", "console.txt") if (self.folder / name).exists()}
            self.fail(f"exit {actual}, expected {expected}; evidence: {preserved}\n"
                      + json.dumps(diagnostics, indent=2))


class FixedReplicaFixture(unittest.TestCase):
    def setUp(self):
        self.sample = three_sample()
        self.identities = records.pilot_identity(self.sample, replicas=3)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def logs(self):
        (self.folder / "pod-logs").mkdir()
        for i in range(1, 4):
            (self.folder / "pod-logs" / f"pod-{i}.log").write_text(
                '2026-10-18T11:59:59Z [GIN] warmup | 200 | 1s | ip | POST "/api/generate"\n'
                '2026-10-18T12:00:01Z [GIN] load | 200 | 1s | ip | POST "/api/generate"\n'
                '2026-10-18T12:00:01Z [GIN] probe | 200 | 1ms | ip | GET "/api/tags"\n', encoding="utf-8")
        return {"initial_identity": self.identities, "load_process_started_at_utc": "2026-10-18T12:00:00Z",
                "load_process_finished_at_utc": "2026-10-18T12:00:02Z"}


class FixedLauncherFixture(unittest.TestCase):
    def run_fixture(self, failed_warmup=False, main=False, replicas=3, profile="steady", diagnostic=None, pilot=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name) / "run"
        logs = {f"pod-{i}": [] for i in range(1, 4)}

        class Handler(BaseHTTPRequestHandler):
            index = 0
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                uid = self.path.split("/")[-1] if self.path.startswith("/warmup/") else f"pod-{Handler.index % replicas + 1}"
                if self.path == "/api/generate": Handler.index += 1
                answer = "" if failed_warmup and uid == "pod-2" else "answer"
                data = json.dumps({"done": True, "response": answer, "eval_count": 56, "load_duration": 0}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                logs[uid].append(f'{run_pilot.utc_now()} [GIN] test | 200 | 1ms | ip | POST "/api/generate"\n')
                self.server.payloads.append(body)
                self.wfile.write(data)
            def log_message(self, *args): pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.payloads = []
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def close():
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.addCleanup(close)
        base = f"http://127.0.0.1:{server.server_port}"

        class Observer:
            def __init__(self, context, namespace, selector): self.context, self.namespace = context, namespace
            def collect(self, interval):
                current = three_sample(run_pilot.utc_now())
                if replicas == 1:
                    current['pods']['items'] = current['pods']['items'][:1]
                    current['resource_usage'] = [r for r in current['resource_usage'] if r['scope'] == 'node' or r['pod_uid'] == 'pod-1']
                    target = current['deployments']['items'][0]
                    target['spec']['replicas'] = 1
                    target['status'].update(replicas=1, updatedReplicas=1, readyReplicas=1, availableReplicas=1)
                return current
            def read(self, *args):
                if "endpointslices" in args:
                    slices = route()["endpoint_slices"]
                    slices["items"][0]["endpoints"] = slices["items"][0]["endpoints"][:replicas]
                    return json.dumps(slices)
                if "service" in args: return json.dumps(route()["service"])
                name = args[args.index("logs") + 1]
                return "".join(logs[name.replace("ollama-", "pod-")])

        def pod_proxy(command, **kwargs):
            self.assertEqual(command[-2:], ["-f", "-"])
            name = command[command.index("--raw") + 1].split("/pods/")[1].split(":")[0]
            request = urllib.request.Request(base + "/warmup/" + name.replace("ollama-", "pod-"),
                                             data=kwargs["input"].encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response:
                return subprocess.CompletedProcess(command, 0, response.read().decode(), "")

        args = ["--base-url", base, "--replicas", str(replicas), "--rate", "30", "--duration", "1s", "--idle-seconds", "0",
                "--post-seconds", "0", "--run-dir", str(folder)]
        if diagnostic:
            args += ['--diagnostic-warmup-wait', diagnostic, '--observer-interval', '.05']
        if pilot:
            args += ['--pilot-preparation', '--observer-interval', '.05']
        workload_path = Path(run_pilot.__file__).with_name('workload.json')
        workload = json.loads(workload_path.read_text())
        if main:
            # Allow normal Windows scheduling jitter between fixture observations.
            interval = .2
            workload['main_protocol'].update(peak_rate=30, steady_seconds=1, observer_interval_seconds=interval,
                                             idle_seconds=0, fixed_post_seconds=0)
            for stage, seconds in zip(workload['burst_stages'], (.2, .05, 1.5, .05, .2)):
                stage['seconds'] = seconds
            planned = (1 if replicas == 1 else 2) + (3 if profile == 'burst' else 0)
            args += ['--protocol-version', '1.1', '--profile', profile, '--observer-interval', str(interval),
                     '--repetition', '1', '--planned-order', str(planned), '--actual-order', '1']
            if profile == 'burst':
                index = args.index('--duration')
                del args[index:index+2]
        original_read, original_copy = Path.read_text, shutil.copyfile
        def read(path, *a, **kw):
            return json.dumps(workload) if main and path == workload_path else original_read(path, *a, **kw)
        def copy(source, destination, *a, **kw):
            if main and Path(source) == workload_path:
                Path(destination).write_text(json.dumps(workload))
                return destination
            return original_copy(source, destination, *a, **kw)
        versions = {k: {"exit_code": 0} for k in ("k6", "kubectl", "minikube", "docker")}
        with patch.object(run_pilot, "Observer", Observer), patch.object(run_pilot, "versions", return_value=versions), \
                patch.object(fixed_replicas.subprocess, "run", side_effect=pod_proxy), \
                patch('main_protocol.source_revision', return_value={'commit': 'local-test-fixture', 'dirty': False}), \
                patch('main_protocol.recover', return_value={'test_stub': True}), \
                patch('main_protocol.prepare_fixed'), patch('main_protocol.check_configuration'), \
                patch('main_protocol.runtime_context', return_value={'test_stub': True}), \
                patch('main_protocol.settle', return_value={'test_stub': True}), \
                patch.object(Path, 'read_text', read), patch.object(shutil, 'copyfile', copy):
            if failed_warmup:
                with patch.object(run_pilot, "run_load") as load, patch.object(run_pilot.shutil, "which", return_value="test-k6"):
                    code = run_pilot.main(args)
                    load.assert_not_called()
            else:
                code = run_pilot.main(args)
        return folder, code, server.payloads


class AutoscalingFixture(unittest.TestCase):
    def exercise(self, interrupt=False, fail_warmup=False, profile="burst", main=False, latency_target=None, startup_delay=0, pilot=False):
        import time
        import shutil
        fixture = PilotLauncherFixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        captured = fixture.server(fail_warmup=fail_warmup)
        workload_path = Path(run_pilot.__file__).parent / 'workload.json'
        workload = json.loads(workload_path.read_text())
        for stage, seconds in zip(workload['burst_stages'], (.2, .05, .5, .05, .2)):
            stage['seconds'] = seconds
        if main:
            workload["main_protocol"].update(peak_rate=30, steady_seconds=1, observer_interval_seconds=.05, idle_seconds=0, hpa_post_seconds=1)
        if latency_target is not None:
            workload["main_protocol"]["primary_p95_ms"] = latency_target
        original_read, original_copy = Path.read_text, shutil.copyfile

        def read(path, *args, **kwargs):
            if path == workload_path:
                return json.dumps(workload)
            return original_read(path, *args, **kwargs)

        def copy(source, destination, *args, **kwargs):
            if Path(source) == workload_path:
                Path(destination).write_text(json.dumps(workload))
                return destination
            return original_copy(source, destination, *args, **kwargs)

        # Keep fixture timestamps on a precise elapsed clock, even on coarse wall clocks.
        origin = datetime.now(timezone.utc)
        origin_counter = time.perf_counter_ns()

        def observation_time():
            return (origin + timedelta(microseconds=(time.perf_counter_ns() - origin_counter) // 1000)).isoformat()

        class Observer:
            applied = None
            load_samples = 0
            def __init__(self, context, namespace, selector):
                self.context, self.namespace, self.selector = context, namespace, selector
            def collect(self, interval):
                current = sample(observation_time())
                if Observer.applied is not None:
                    # The first request warms the model; later requests are measured traffic.
                    # Advance on collected samples so k6 startup time cannot consume the transition.
                    if len(captured) > 1:
                        Observer.load_samples += 1
                    count = 2 if 1 <= Observer.load_samples <= 3 else 1
                    if count == 2:
                        current = three_sample(current["time"])
                        current['pods']['items'] = current['pods']['items'][:2]
                        current['deployments']['items'][0]['spec']['replicas'] = 2
                    current['hpa']['items'] = [hpa()]
                    current['hpa']['items'][0]['status'].update(currentReplicas=count, desiredReplicas=count)
                return current
            def read(self, *args):
                if 'apply' in args:
                    Observer.applied = time.monotonic()
                    return 'applied'
                if 'delete' in args:
                    Observer.applied = None
                    return 'deleted'
                if 'scale' in args: return 'scaled'
                if 'endpointslices' in args:
                    return json.dumps({'items': [{'endpoints': [{'conditions': {'ready': True}, 'targetRef': {'kind': 'Pod', 'uid': 'pod-1'}}]}]})
                if 'service' in args:
                    return json.dumps({'spec': {'selector': {'app': 'ollama'}, 'ports': [{'port': 11434, 'targetPort': 11434}]}})
                if 'hpa' in args and 'ollama' in args: return json.dumps(hpa())
                kind = next(x for x in ('deployment', 'pods', 'hpa') if x in args)
                return json.dumps(self.collect(5)[{'deployment': 'deployments', 'pods': 'pods', 'hpa': 'hpa'}[kind]])

        class Logs:
            def __init__(self, observer, folder, container):
                self.folder = folder
                self.records = {}
                self.stopped = False
                (folder / 'pod-logs').mkdir()
            def update(self, sample):
                for p in sample['pods']['items']:
                    uid = p['metadata']['uid']
                    self.records[uid] = {'pod_name': p['metadata']['name'], 'complete': True,
                                         'exit_code': 1, 'stopped_by_collector': True}
                    (self.folder / 'pod-logs' / (uid + '.log')).touch()
            def stop(self):
                self.stopped = True
                (self.folder / 'log-coverage.json').write_text(json.dumps(self.records))

        original_load = run_pilot.run_load

        def delayed_load(command, environment, folder, collection, metadata):
            collection.wait(startup_delay)
            return original_load(command, environment, folder, collection, metadata)

        args = fixture.args[:]
        args[args.index('--post-seconds') + 1] = '1'
        index = args.index('--duration')
        del args[index:index+2]
        args += ['--mode', 'autoscaling', '--profile', profile, '--rate', '30', '--observer-interval', '.05']
        if profile == 'steady':
            args += ['--duration', '1s']
        if main:
            args += ['--protocol-version', '1.1', '--repetition', '1', '--planned-order', '3' if profile == 'steady' else '6', '--actual-order', '1']
        if pilot:
            args += ['--pilot-preparation']
        with patch.object(run_pilot, 'run_load', delayed_load), \
             patch.object(run_pilot, 'Observer', Observer), patch.object(run_pilot, 'versions', fixture.fake_versions), \
             patch.object(autoscaling, 'Logs', Logs), patch.object(Path, 'read_text', read), \
             patch.object(run_pilot.shutil, 'copyfile', copy), \
             patch.object(run_pilot.shutil, 'which', return_value=shutil.which('k6') or 'test-k6'), \
             patch('main_protocol.recover', return_value={'test_stub': True}), \
             patch('main_protocol.runtime_context', return_value={'test_stub': True}), \
             patch('main_protocol.check_configuration') as configuration, \
             patch('main_protocol.settle', return_value={'test_stub': True}) as settle:
            if interrupt:
                with patch.object(run_pilot, 'run_load', side_effect=KeyboardInterrupt):
                    code = run_pilot.main(args)
            else:
                code = run_pilot.main(args)
        if (main or pilot) and not interrupt and not fail_warmup:
            self.assertEqual(settle.call_count, 2)
            self.assertFalse(settle.call_args_list[0].args[2:] or ())
            self.assertEqual(settle.call_args_list[1].args[2:], (True,))
        return fixture.folder, code

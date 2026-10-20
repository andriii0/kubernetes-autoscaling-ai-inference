import copy
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import analyze
import fixed_replicas
import pilot_records
import run_pilot
from test_pilot_records import sample


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
                  "cpu_timestamp_ms": pilot_records.timestamp(at) * 1000,
                  "memory_timestamp_ms": pilot_records.timestamp(at) * 1000}
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


class FixedReplicaTests(unittest.TestCase):
    def setUp(self):
        self.sample = three_sample()
        self.identities = pilot_records.pilot_identity(self.sample, replicas=3)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def test_identity_is_order_independent_but_restart_or_replacement_is_visible(self):
        self.sample["pods"]["items"].reverse()
        self.assertEqual(self.identities, pilot_records.pilot_identity(self.sample, replicas=3))
        self.sample["pods"]["items"][0]["status"]["containerStatuses"][0]["restartCount"] += 1
        self.assertNotEqual(self.identities, pilot_records.pilot_identity(self.sample, replicas=3))

    def test_missing_unready_duplicate_and_incomplete_resource_pods_are_rejected(self):
        for case in ("missing", "unready", "duplicate", "resource", "stale", "hpa"):
            with self.subTest(case=case):
                current = copy.deepcopy(self.sample)
                if case == "missing":
                    current["pods"]["items"].pop()
                elif case == "unready":
                    current["pods"]["items"][1]["status"]["containerStatuses"][0]["ready"] = False
                elif case == "duplicate":
                    current["pods"]["items"][1] = copy.deepcopy(current["pods"]["items"][0])
                elif case == "resource":
                    current["resource_usage"].pop()
                elif case == "stale":
                    current["deployments"]["items"][0]["status"]["updatedReplicas"] = 2
                else:
                    current["hpa"]["items"] = [{"spec": {"scaleTargetRef": {"kind": "Deployment", "name": "ollama"}}}]
                with self.assertRaises(ValueError):
                    pilot_records.pilot_identity(current, replicas=3)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            pilot_records.pilot_identity(self.sample)

    def test_service_requires_all_and_only_ready_selected_pods(self):
        target = self.sample["deployments"]["items"][0]
        fixed_replicas.check_route(route(), self.identities, target)
        for case in ("missing", "foreign", "unready", "selector", "port"):
            with self.subTest(case=case):
                current = route()
                endpoints = current["endpoint_slices"]["items"][0]["endpoints"]
                if case == "missing": endpoints.pop()
                if case == "foreign": endpoints[0]["targetRef"]["uid"] = "other"
                if case == "unready": endpoints[0]["conditions"]["ready"] = False
                if case == "selector": current["service"]["spec"]["selector"] = {"app": "other"}
                if case == "port": current["service"]["spec"]["ports"][0]["targetPort"] = 8080
                with self.assertRaises(ValueError):
                    fixed_replicas.check_route(current, self.identities, target)

    def test_warmup_must_cover_each_pod_and_finish_before_load(self):
        warm = {"replicas": [{"pod_uid": f"pod-{i}", "successful": True, "http_status": 200,
                              "finished_at_utc": "2026-10-18T12:00:00Z"} for i in range(1, 4)]}
        fixed_replicas.check_warmup(warm, self.identities, "2026-10-18T12:00:01Z")
        for case in ("missing", "duplicate", "failed", "overlap"):
            with self.subTest(case=case):
                current = copy.deepcopy(warm)
                if case == "missing": current["replicas"].pop()
                if case == "duplicate": current["replicas"][1]["pod_uid"] = "pod-1"
                if case == "failed": current["replicas"][1]["successful"] = False
                if case == "overlap": current["replicas"][1]["finished_at_utc"] = "2026-10-18T12:00:02Z"
                with self.assertRaises(ValueError):
                    fixed_replicas.check_warmup(current, self.identities, "2026-10-18T12:00:01Z")

    def logs(self):
        (self.folder / "pod-logs").mkdir()
        for i in range(1, 4):
            (self.folder / "pod-logs" / f"pod-{i}.log").write_text(
                '2026-10-18T11:59:59Z [GIN] warmup | 200 | 1s | ip | POST "/api/generate"\n'
                '2026-10-18T12:00:01Z [GIN] load | 200 | 1s | ip | POST "/api/generate"\n'
                '2026-10-18T12:00:01Z [GIN] probe | 200 | 1ms | ip | GET "/api/tags"\n', encoding="utf-8")
        return {"initial_identity": self.identities, "load_process_started_at_utc": "2026-10-18T12:00:00Z",
                "load_process_finished_at_utc": "2026-10-18T12:00:02Z"}

    def test_access_logs_exclude_warmup_and_readiness_and_reconcile_client_counts(self):
        metadata = self.logs()
        result = fixed_replicas.distribution(self.folder, metadata, {"completed": 3, "successful": 3}, [{"http_status": 200}] * 3)
        self.assertEqual([v["completed"] for v in result["pods"].values()], [1, 1, 1])
        for counts, statuses in (({"completed": 4, "successful": 3}, [200] * 3),
                                 ({"completed": 3, "successful": 2}, [200, 200, 503])):
            with self.assertRaises(ValueError):
                fixed_replicas.distribution(self.folder, metadata, counts, [{"http_status": s} for s in statuses])
        # A malformed/empty HTTP-200 body is a client failure, not missing Service traffic.
        result = fixed_replicas.distribution(self.folder, metadata, {"completed": 3, "successful": 2},
                                             [{"http_status": 200}] * 3)
        self.assertEqual(sum(p["completed"] for p in result["pods"].values()), 3)
        path = self.folder / "pod-logs/pod-2.log"
        original = path.read_text()
        path.write_text("")
        with self.assertRaisesRegex(ValueError, "not every replica"):
            fixed_replicas.distribution(self.folder, metadata, {"completed": 3, "successful": 3}, [{"http_status": 200}] * 3)
        path.write_text(original.replace("[GIN] load | 200 |", "unknown"))
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            fixed_replicas.distribution(self.folder, metadata, {"completed": 3, "successful": 3}, [{"http_status": 200}] * 3)
        path.unlink()
        with self.assertRaises(OSError):
            fixed_replicas.distribution(self.folder, metadata, {"completed": 3, "successful": 3}, [{"http_status": 200}] * 3)

    def test_three_pod_resource_sum_requires_complete_aligned_samples(self):
        data = {"metadata": {"initial_identity": self.identities, "namespace": "inference", "container": "ollama"},
                "cluster": [self.sample]}
        point = analyze.resource_points(data)[0]
        self.assertEqual((point["cpu"], point["memory"], point["ready"]), (6, 6 * 2**20, 3))
        self.sample["resource_usage"][2]["cpu_cores"] = None
        self.assertIsNone(analyze.resource_points(data)[0]["cpu"])
        self.sample["resource_usage"][2]["memory_timestamp_ms"] += 1
        self.assertIsNone(analyze.resource_points(data)[0]["memory"])
        data["check"] = {"load_window": {"started_at_utc": "2026-10-18T11:59:59Z",
                                         "client_drain_end_at_utc": "2026-10-18T12:00:02Z"}}
        per_pod = analyze.replica_resources(data)
        self.assertEqual(per_pod["pod-1"]["cpu_mean_cores"], 1)
        self.assertIsNone(per_pod["pod-2"]["cpu_mean_cores"])
        self.assertEqual(per_pod["pod-2"]["peak_memory_mib"], 2)

    def test_three_replica_observer_stops_after_a_restart(self):
        class Observer:
            def collect(inner, interval):
                current = copy.deepcopy(self.sample)
                current["time"] = run_pilot.utc_now()
                return current
        collection = run_pilot.Collection(Observer(), self.folder, .01, "ollama", "ollama", 3)
        collection.start()
        try:
            self.sample["pods"]["items"][1]["status"]["containerStatuses"][0]["restartCount"] += 1
            with self.assertRaisesRegex(RuntimeError, "identity or restart"):
                collection.wait(1)
        finally:
            collection.stop()
        self.assertTrue(collection.failed.is_set())


class FixedLauncherTests(unittest.TestCase):
    def run_fixture(self, failed_warmup=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name) / "run"
        logs = {f"pod-{i}": [] for i in range(1, 4)}

        class Handler(BaseHTTPRequestHandler):
            index = 0
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                uid = self.path.split("/")[-1] if self.path.startswith("/warmup/") else f"pod-{Handler.index % 3 + 1}"
                if self.path == "/api/generate": Handler.index += 1
                answer = "" if failed_warmup and uid == "pod-2" else "answer"
                data = json.dumps({"done": True, "response": answer, "eval_count": 56, "load_duration": 0}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                logs[uid].append(f'{run_pilot.utc_now()} [GIN] test | 200 | 1ms | ip | POST "/api/generate"\n')
                self.server.payloads.append(body)
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
            def collect(self, interval): return three_sample(run_pilot.utc_now())
            def read(self, *args):
                if "endpointslices" in args: return json.dumps(route()["endpoint_slices"])
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

        args = ["--base-url", base, "--replicas", "3", "--rate", "30", "--duration", "1s", "--idle-seconds", "0",
                "--post-seconds", "0", "--run-dir", str(folder)]
        versions = {k: {"exit_code": 0} for k in ("k6", "kubectl", "minikube", "docker")}
        with patch.object(run_pilot, "Observer", Observer), patch.object(run_pilot, "versions", return_value=versions), \
                patch.object(fixed_replicas.subprocess, "run", side_effect=pod_proxy):
            if failed_warmup:
                with patch.object(run_pilot, "run_load") as load, patch.object(run_pilot.shutil, "which", return_value="test-k6"):
                    code = run_pilot.main(args)
                    load.assert_not_called()
            else:
                code = run_pilot.main(args)
        return folder, code, server.payloads

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
    def test_real_k6_lifecycle_with_three_pod_warmups_and_service_distribution(self):
        folder, code, payloads = self.run_fixture()
        report = json.loads((folder / "collection-check.json").read_text())
        self.assertEqual(code, 0, report)
        self.assertTrue(report["valid"], report)
        self.assertEqual(len(report["distribution"]["pods"]), 3)
        metadata = json.loads((folder / "metadata.json").read_text())
        self.assertEqual(metadata["mode"], "fixed-3")
        self.assertEqual(len(payloads), report["counts"]["completed"] + 3)
        self.assertTrue(all(p == metadata["workload"]["request"] for p in payloads))
        self.assertTrue(analyze.calculate_metrics(analyze.load_results(folder))["collection_valid"])
        original = (folder / "request-events.jsonl").read_bytes()
        destination = folder / "analysis"
        self.assertEqual(analyze.main([str(folder), "--output-dir", str(destination), "--no-plots"]), 0)
        per_pod = json.loads((destination / "per-replica-resources.json").read_text())
        self.assertEqual(set(per_pod[folder.name]), {"pod-1", "pod-2", "pod-3"})
        self.assertEqual(original, (folder / "request-events.jsonl").read_bytes())
        warm_path = folder / "warmup.json"
        warm = json.loads(warm_path.read_text())
        warm["replicas"].pop()
        warm_path.write_text(json.dumps(warm))
        self.assertFalse(pilot_records.reconcile(folder, metadata)["valid"])

    def test_second_pod_warmup_failure_preserves_records_and_never_loads(self):
        folder, code, payloads = self.run_fixture(failed_warmup=True)
        self.assertEqual(code, 1)
        warm = json.loads((folder / "warmup.json").read_text())
        self.assertFalse(warm["successful"])
        self.assertEqual(len(warm["replicas"]), 2)
        self.assertEqual(len(payloads), 2)
        self.assertFalse(json.loads((folder / "metadata.json").read_text())["collection_valid"])


if __name__ == "__main__":
    unittest.main()

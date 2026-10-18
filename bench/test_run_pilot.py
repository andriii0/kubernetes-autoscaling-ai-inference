import argparse
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

import run_pilot
from test_pilot_records import sample


class FakeObserver:
    broken = False

    def __init__(self, context, namespace, selector):
        self.context, self.namespace, self.selector = context, namespace, selector

    def collect(self, interval):
        result = sample(run_pilot.utc_now())
        if self.broken:
            result["errors"] = [{"source": "test", "message": "unavailable"}]
        return result


class PilotLauncherTests(unittest.TestCase):
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
        with patch.object(run_pilot, "Observer", FakeObserver), patch.object(run_pilot, "versions", self.fake_versions):
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

    def test_real_k6_full_lifecycle_and_complete_evidence(self):
        captured = self.server()
        with patch.dict(os.environ, {"K6_ITERATIONS": "1000", "K6_DURATION": "3m", "K6_OUT": "unexpected", "PROFILE": "burst", "SLO_MS": "1"}):
            self.assert_run_exit(0)
        metadata = self.metadata()
        self.assertEqual(metadata["status"], "finished")
        self.assertTrue(metadata["collection_valid"], metadata)
        self.assertEqual([p["phase"] for p in metadata["phases"]], ["idle", "warmup", "load", "post_load", "validation"])
        self.assertEqual(metadata["k6_exit_code"], 0)
        self.assertEqual(metadata["collector_exit_code"], 0)
        self.assertEqual(metadata["warnings"], [])
        self.assertEqual(len(captured), metadata["counts"]["completed"] + 1)
        self.assertTrue(all(p == metadata["workload"]["request"] for p in captured))
        for name in ("warmup.json", "cluster-before.json", "cluster-after.json", "cluster.jsonl", "requests.json",
                     "request-events.jsonl", "summary.json", "console.txt", "collection-check.json"):
            self.assertTrue((self.folder / name).is_file(), name)
        for name, digest in metadata["source_sha256"].items():
            self.assertEqual(run_pilot.hashlib.sha256((self.folder / "inputs" / name).read_bytes()).hexdigest(), digest)
        self.assertIsNotNone(metadata["load_window"])
        self.assertFalse(any(t.name == "pilot-observer" for t in threading.enumerate()))

    def test_threshold_failure_keeps_valid_measured_evidence(self):
        self.server(fail_after_warmup=True)
        self.assert_run_exit(99)
        metadata = self.metadata()
        self.assertEqual(metadata["status"], "thresholds_failed")
        self.assertTrue(metadata["collection_valid"], metadata)
        self.assertEqual(metadata["counts"]["failed"], metadata["counts"]["completed"])
        self.assertEqual(metadata["counts"]["successful"], 0)

    def test_existing_run_is_unchanged_and_nothing_is_started(self):
        self.folder.mkdir()
        evidence = self.folder / "requests.json"
        evidence.write_bytes(b"previous measured data")
        with patch.object(run_pilot.subprocess, "Popen") as execute:
            self.assertEqual(run_pilot.main(self.args), 2)
            execute.assert_not_called()
        self.assertEqual(evidence.read_bytes(), b"previous measured data")
        self.assertEqual(list(self.folder.iterdir()), [evidence])

        # Cover empty directories and regular files with the same no-launch oracle.
        evidence.unlink()
        with patch.object(run_pilot.subprocess, "Popen") as execute:
            self.assertEqual(run_pilot.main(self.args), 2)
            self.folder.rmdir()
            self.folder.write_bytes(b"existing file")
            self.assertEqual(run_pilot.main(self.args), 2)
            self.assertEqual(self.folder.read_bytes(), b"existing file")
            execute.assert_not_called()

    def test_missing_k6_preserves_failure_metadata(self):
        with patch.object(run_pilot.shutil, "which", return_value=None):
            self.assertEqual(run_pilot.main(self.args), 1)
        metadata = self.metadata()
        self.assertEqual(metadata["status"], "failed")
        self.assertIsNone(metadata["k6_exit_code"])
        self.assertIn("PATH", metadata["errors"][0])
        self.assertFalse(metadata["collection_valid"])

    def test_invalid_preflight_retains_snapshot_and_never_loads(self):
        FakeObserver.broken = True
        with patch.object(run_pilot, "run_load") as execute:
            self.assertEqual(self.invoke(), 1)
            execute.assert_not_called()
        self.assertTrue((self.folder / "cluster-before.json").exists())
        self.assertTrue((self.folder / "cluster.jsonl").read_text())
        self.assertFalse(self.metadata()["collection_valid"])

    def test_failed_warmup_never_starts_k6(self):
        self.server(fail_warmup=True)
        with patch.object(run_pilot, "run_load") as execute:
            self.assertEqual(self.invoke(), 1)
            execute.assert_not_called()
        warmup = json.loads((self.folder / "warmup.json").read_text())
        self.assertFalse(warmup["successful"])
        self.assertEqual(warmup["http_status"], 503)
        self.assertTrue((self.folder / "cluster-after.json").exists())

    def test_interrupt_preserves_records_and_stops_observer(self):
        self.server()
        with patch.object(run_pilot, "run_load", side_effect=KeyboardInterrupt):
            self.assertEqual(self.invoke(), 130)
        self.assertEqual(self.metadata()["status"], "interrupted")
        self.assertTrue((self.folder / "cluster-after.json").exists())
        self.assertFalse(any(t.name == "pilot-observer" for t in threading.enumerate()))

    def test_background_collection_error_is_detected(self):
        observer = FakeObserver("ai-lab", "inference", "app=ollama")
        self.folder.mkdir()
        collection = run_pilot.Collection(observer, self.folder, .01, "ollama", "ollama")
        try:
            collection.start()
            observer.broken = True
            with self.assertRaises(RuntimeError):
                collection.wait(1)
        finally:
            collection.stop()
        self.assertTrue(collection.failed.is_set())
        self.assertTrue(collection.errors)

    def test_duration_validation(self):
        self.assertEqual(run_pilot.duration_seconds("1m30s"), 90)
        self.assertEqual(run_pilot.duration_seconds("250ms"), .25)
        for value in ("0s", "-1s", "NaN", "infinity", "3d", "1mgarbage"):
            with self.assertRaises(argparse.ArgumentTypeError):
                run_pilot.duration_seconds(value)

    def test_running_k6_is_stopped_after_observer_failure(self):
        self.folder.mkdir()
        process = Mock()
        process.poll.return_value = None
        process.returncode = None

        def wait(**kwargs):
            process.returncode = -15
            return -15

        process.wait.side_effect = wait
        collection = Mock()
        collection.wait.side_effect = RuntimeError("observer unavailable")
        metadata = {"duration_seconds": 1, "workload": {"graceful_stop_seconds": 35}}
        with patch.object(run_pilot.subprocess, "Popen", return_value=process), self.assertRaises(RuntimeError):
            run_pilot.run_load(["k6"], {}, self.folder, collection, metadata)
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)
        self.assertEqual(metadata["k6_exit_code"], -15)
        self.assertIn("load_process_finished_at_utc", metadata)

    def test_failed_version_diagnostics_do_not_stop_real_load(self):
        self.server()
        with patch.object(self, "fake_versions", return_value={"k6": {"exit_code": 2, "stderr": "version command failed"}}):
            self.assert_run_exit(0)
        self.assertEqual(self.metadata()["versions"]["k6"]["exit_code"], 2)
        self.assertEqual(self.metadata()["k6_exit_code"], 0)
        self.assertTrue(self.metadata()["collection_valid"])
        self.assertTrue(self.metadata()["warnings"])

    def test_scheduler_pause_exposes_test_only_interval_without_weakening_real_rule(self):
        self.server()
        original_run = run_pilot.Collection._run

        def delayed_run(collection):
            time.sleep(.45)
            original_run(collection)

        # A 450-ms scheduling delay breaks the former artificial 400-ms gap budget.
        # The actual pilot uses a 5-s interval / 10-s budget; that rule is unchanged.
        arguments = list(self.args)
        for interval, expected in ((.2, 1), (5, 0)):
            with self.subTest(interval=interval):
                self.folder = self.folder.parent / f"interval-{interval}"
                self.args = arguments + ["--observer-interval", str(interval)]
                self.args[self.args.index("--run-dir") + 1] = str(self.folder)
                with patch.object(run_pilot.Collection, "_run", delayed_run):
                    self.assert_run_exit(expected)
                report = json.loads((self.folder / "collection-check.json").read_text())
                if interval == .2:
                    self.assertEqual(report["errors"], ["observation gap exceeds twice the configured interval"])
                else:
                    self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()

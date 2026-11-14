import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

import run_pilot
from tests.bench.fixtures import PilotLauncherFixture, FakeObserver


class PilotLauncherTests(PilotLauncherFixture):
    def test_source_archives_import_without_the_checkout(self):
        variants = ((), ('--mode', 'fixed-3'), ('--mode', 'autoscaling'), ('--pilot-preparation',))
        for index, extra in enumerate(variants):
            with self.subTest(options=extra):
                args, workload, seconds, prepared = run_pilot.parse_arguments(self.args + list(extra))
                args.run_dir = self.folder.parent / f'archive-{index}'
                args.run_dir.mkdir()
                metadata = run_pilot.create_metadata(args, workload, seconds)
                with patch('main_protocol.source_revision', return_value={'commit': 'fixture', 'dirty': False}):
                    inputs, _ = run_pilot.archive_inputs(args, metadata, prepared)
                self.assertEqual(metadata['source_archive_version'], 2)
                self.assertIn('records.py', metadata['source_sha256'])
                modules = 'import run_pilot, pilot_records, records'
                if prepared:
                    modules += ', main_protocol, analyze'
                if args.mode == 'autoscaling':
                    modules += ', autoscaling, fixed_replicas'
                script = 'import sys; sys.path.insert(0, sys.argv[1]); ' + modules
                result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(inputs)],
                                        cwd=inputs, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)


    def test_explicit_slo_is_passed_and_ambient_overrides_stay_blocked(self):
        args = argparse.Namespace(base_url='http://localhost:1', rate=2, duration='1s', slo_ms=None)
        with patch.dict(os.environ, {'SLO_MS': '1', 'K6_DURATION': '9h', 'GATEWAY_REQUEST_IDS': '1'}):
            environment = run_pilot.load_environment(args, 'test-run')
            self.assertNotIn('SLO_MS', environment)
            self.assertNotIn('K6_DURATION', environment)
            self.assertNotIn('GATEWAY_REQUEST_IDS', environment)
            args.slo_ms = 3000
            self.assertEqual(run_pilot.load_environment(args, 'test-run')['SLO_MS'], '3000')

    def test_invalid_slo_is_rejected_before_creating_run_or_observer(self):
        with patch.object(run_pilot, 'Observer') as observer:
            for value in ('0', '-1', 'nan', 'inf', 'text'):
                with self.subTest(value=value), self.assertRaises(SystemExit):
                    run_pilot.main(self.args + ['--slo-ms', value])
                self.assertFalse(self.folder.exists())
            observer.assert_not_called()

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
    def test_explicit_latency_threshold_fails_without_invalidating_collection(self):
        captured = self.server()
        self.args += ['--slo-ms', '0.000001']
        self.assert_run_exit(99)
        metadata = self.metadata()
        self.assertEqual(metadata['slo_ms'], 0.000001)
        self.assertTrue(metadata['collection_valid'], metadata)
        self.assertEqual(metadata['counts']['failed'], 0)
        self.assertGreater(len(captured), 1)
        summary = json.loads((self.folder / 'summary.json').read_text())
        self.assertGreater(summary['metrics']['successful_latency_ms']['p(95)'], metadata['slo_ms'])


    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
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

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
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
        with patch("build_k6.runtime", side_effect=ValueError("Build the monotonic k6 runtime first")):
            self.assertEqual(run_pilot.main(self.args), 1)
        metadata = self.metadata()
        self.assertEqual(metadata["status"], "failed")
        self.assertIsNone(metadata["k6_exit_code"])
        self.assertIn("monotonic k6 runtime", metadata["errors"][0])
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

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
    def test_failed_version_diagnostics_do_not_stop_real_load(self):
        self.server()
        with patch.object(self, "fake_versions", return_value={"k6": {"exit_code": 2, "stderr": "version command failed"}}):
            self.assert_run_exit(0)
        self.assertEqual(self.metadata()["versions"]["k6"]["exit_code"], 2)
        self.assertEqual(self.metadata()["k6_exit_code"], 0)
        self.assertTrue(self.metadata()["collection_valid"])
        self.assertTrue(self.metadata()["warnings"])

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
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

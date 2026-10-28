import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import analyze
import fixed_replicas
import pilot_records
import records
import run_pilot
from tests.bench.fixtures import FixedReplicaFixture, FixedLauncherFixture
from tests.bench.fixtures import route


class FixedReplicaTests(FixedReplicaFixture):
    def test_identity_is_order_independent_but_restart_or_replacement_is_visible(self):
        self.sample["pods"]["items"].reverse()
        self.assertEqual(self.identities, records.pilot_identity(self.sample, replicas=3))
        self.sample["pods"]["items"][0]["status"]["containerStatuses"][0]["restartCount"] += 1
        self.assertNotEqual(self.identities, records.pilot_identity(self.sample, replicas=3))

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
                    records.pilot_identity(current, replicas=3)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            records.pilot_identity(self.sample)

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


class FixedLauncherTests(FixedLauncherFixture):
    def test_prepared_load_failure_still_captures_fixed_pod_logs(self):
        with patch.object(run_pilot, 'run_load', side_effect=RuntimeError('simulated load failure')), \
                patch.object(run_pilot.shutil, 'which', return_value='test-k6'):
            folder, code, _ = self.run_fixture(main=True, replicas=1)
        self.assertEqual(code, 1)
        metadata = json.loads((folder / 'metadata.json').read_text())
        self.assertIn('simulated load failure', metadata['errors'])
        self.assertTrue((folder / 'pod-logs/pod-1.log').is_file())
        self.assertFalse(any('final fixed-mode logs' in error for error in metadata['errors']))

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

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
    def test_diagnostic_variants_reuse_preparation_and_only_quiet_adds_post_warmup_gate(self):
        for variant in ('immediate', 'quiet'):
            with self.subTest(variant=variant):
                folder, code, payloads = self.run_fixture(replicas=1, diagnostic=variant)
                metadata = json.loads((folder / 'metadata.json').read_text())
                report = json.loads((folder / 'collection-check.json').read_text())
                self.assertEqual(code, 0, report)
                self.assertTrue(report['valid'], report)
                self.assertEqual(metadata['purpose'], 'diagnostic-warmup-wait')
                self.assertEqual(metadata['diagnostic_warmup_wait'], variant)
                self.assertNotIn('protocol_version', metadata)
                self.assertFalse((folder / 'assessment.json').exists())
                phases = [p['phase'] for p in metadata['phases']]
                self.assertIn('recovery_quiet', phases)
                self.assertIn('initial_quiet', phases)
                self.assertEqual('post_warmup_quiet' in phases, variant == 'quiet')
                self.assertEqual(len(payloads), report['counts']['completed'] + 1)
                self.assertTrue(all(p == metadata['workload']['request'] for p in payloads))
                self.assertIsNotNone(metadata['scheduled_profile_finished_at_utc'])
                self.assertTrue({'main_protocol.py', 'analyze.py', 'fixed_replicas.py'} <= set(metadata['source_sha256']))

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
    def test_fresh_pilot_reuses_prepared_path_without_main_metadata(self):
        folder, code, payloads = self.run_fixture(replicas=1, pilot=True)
        metadata = json.loads((folder / 'metadata.json').read_text())
        report = json.loads((folder / 'collection-check.json').read_text())
        self.assertEqual(code, 0, report)
        self.assertTrue(report['valid'], report)
        self.assertEqual(metadata['purpose'], 'pilot-recalibration')
        self.assertNotIn('protocol_version', metadata)
        self.assertNotIn('diagnostic_warmup_wait', metadata)
        self.assertIn('post_warmup_quiet', [p['phase'] for p in metadata['phases']])
        self.assertEqual(len(payloads), report['counts']['completed'] + 1)

    def test_fresh_pilot_rejects_conflicting_options_before_creating_output(self):
        for extra in (['--protocol-version', '1.1'], ['--diagnostic-warmup-wait', 'quiet'],
                      ['--mode', 'autoscaling'], ['--profile', 'burst']):
            with tempfile.TemporaryDirectory() as temporary, self.subTest(extra=extra):
                folder = Path(temporary) / 'run'
                with patch.object(run_pilot, 'Observer') as observer, self.assertRaises(SystemExit):
                    run_pilot.main(['--base-url', 'http://127.0.0.1:1', '--rate', '8',
                                    '--run-dir', str(folder), '--pilot-preparation'] + extra)
                observer.assert_not_called()
                self.assertFalse(folder.exists())

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
    def test_prepared_fixed_three_keeps_per_pod_warmup_distribution_and_quiet_gates(self):
        folder, code, payloads = self.run_fixture(replicas=3, pilot=True)
        metadata = json.loads((folder / 'metadata.json').read_text())
        report = json.loads((folder / 'collection-check.json').read_text())
        warm = json.loads((folder / 'warmup.json').read_text())
        self.assertEqual(code, 0, report)
        self.assertTrue(report['valid'], report)
        self.assertEqual(metadata['purpose'], 'preliminary-fixed-replica-check')
        self.assertNotIn('protocol_version', metadata)
        self.assertEqual(metadata['expected_replicas'], 3)
        self.assertEqual(len(warm['replicas']), 3)
        self.assertEqual(len(report['distribution']['pods']), 3)
        self.assertTrue(all(p['completed'] > 0 for p in report['distribution']['pods'].values()))
        self.assertEqual(len(payloads), report['counts']['completed'] + 3)
        phases = {p['phase'] for p in metadata['phases']}
        self.assertTrue({'recovery_quiet', 'initial_quiet', 'post_warmup_quiet'} <= phases)

    def test_diagnostic_rejects_main_protocol_and_other_modes_before_creating_output(self):
        for extra in (['--protocol-version', '1.1'], ['--mode', 'autoscaling'], ['--mode', 'fixed-3'], ['--profile', 'burst']):
            with tempfile.TemporaryDirectory() as temporary, self.subTest(extra=extra):
                folder = Path(temporary) / 'run'
                args = ['--base-url', 'http://127.0.0.1:1', '--rate', '8', '--run-dir', str(folder),
                        '--diagnostic-warmup-wait', 'immediate'] + extra
                with patch.object(run_pilot, 'Observer') as observer, self.assertRaises(SystemExit):
                    run_pilot.main(args)
                observer.assert_not_called()
                self.assertFalse(folder.exists())

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

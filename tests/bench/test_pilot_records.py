import copy
import hashlib
import json
import unittest

import pilot_records
import records
from tests.bench.fixtures import RunFixture, sample


class RecordTests(RunFixture):
    def test_new_source_archives_require_records_without_changing_legacy_checks(self):
        self.assertFalse(self.check()['warnings'])
        self.metadata['source_archive_version'] = 2
        self.assertIn('incomplete executable input hashes', self.check()['warnings'])
        helper = self.folder / 'inputs/records.py'
        helper.write_bytes(b'archived helper')
        self.metadata['source_sha256']['records.py'] = hashlib.sha256(helper.read_bytes()).hexdigest()
        self.assertFalse(self.check()['warnings'])
        helper.unlink()
        self.assertTrue(any('input archive:' in warning for warning in self.check()['warnings']))


    def test_valid_collection_and_missing_optional_values(self):
        report = self.check()
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["counts"], {"started": 1, "completed": 1, "successful": 1,
                                           "failed": 0, "unfinished": 0, "dropped": 0})

    def test_unfinished_request_is_visible(self):
        self.assertTrue(self.check()["valid"])
        self.events = [self.start]
        # All k6 counters agree with the partial run: the unmatched start is the only defect.
        for name in ("requests_completed", "http_reqs", "iterations"):
            self.summary["metrics"][name]["count"] = 0
            next(p for p in self.points if p["metric"] == name)["data"]["value"] = 0
        self.summary["metrics"]["inference_errors"] = {"passes": 0, "fails": 0}
        self.remove_latency('request_latency_ms', 'successful_latency_ms')
        report = self.check()
        self.assertFalse(report["valid"])
        self.assertEqual(report["counts"]["unfinished"], 1)
        self.assertEqual(report["errors"], ["1 requests have no completion (server-side drain is unproven)"])

    def test_duplicate_or_orphan_events_are_rejected(self):
        self.assertTrue(self.check()["valid"])
        for events, reason in (([self.completed], "completion without preceding start"),
                               ([self.start, self.start], "duplicate started event"),
                               ([self.start, self.completed, self.completed], "duplicate completed event")):
            with self.subTest(reason=reason):
                self.events = events
                report = self.check()
                self.assertFalse(report["valid"])
                self.assertTrue(any(reason in e for e in report["errors"]), report)

    def test_raw_or_summary_mismatch_is_rejected(self):
        self.assertTrue(self.check()["valid"])
        self.summary["metrics"]["http_reqs"]["count"] = 2
        self.assertEqual(self.check()["errors"], ["http_reqs does not reconcile with request events"])
        self.summary["metrics"]["http_reqs"]["count"] = 1
        self.points[0]["data"]["value"] = 2
        self.assertEqual(self.check()["errors"], ["requests_started does not reconcile with request events"])

    def test_consistent_event_rewrite_cannot_override_independent_k6_latency(self):
        self.assertTrue(self.check()['valid'])
        self.completed.update(duration_ms=1, finished_at_utc='2026-10-18T12:00:01.001Z')
        report = self.check()
        self.assertFalse(report['valid'])
        self.assertIn('successful_latency_ms values do not reconcile with request events', report['errors'])
        self.assertIn('successful_latency_ms summary p(95) does not reconcile with request events', report['errors'])

    def test_missing_duplicate_and_changed_raw_latency_points_are_rejected(self):
        original = copy.deepcopy(self.points)
        for case in ('missing', 'duplicate', 'value'):
            with self.subTest(case=case):
                self.points = copy.deepcopy(original)
                self.assertTrue(self.check()['valid'])
                point = next(p for p in self.points if p['metric'] == 'successful_latency_ms')
                if case == 'missing': self.points.remove(point)
                if case == 'duplicate': self.points.append(copy.deepcopy(point))
                if case == 'value': point['data']['value'] = 1
                self.assertFalse(self.check()['valid'])

    def test_latency_summary_and_explicit_export_tolerance_are_checked(self):
        self.assertTrue(self.check()['valid'])
        for name in ('avg', 'p(95)'):
            self.summary['metrics']['successful_latency_ms'][name] = 1
            report = self.check()
            self.assertFalse(report['valid'])
            self.assertIn(f'successful_latency_ms summary {name} does not reconcile with request events', report['errors'])
            self.summary['metrics']['successful_latency_ms'][name] = 500
        self.completed['duration_ms'] = 500 + pilot_records.LATENCY_TOLERANCE_MS / 2
        self.assertTrue(self.check()['valid'])
        self.completed['duration_ms'] = 500.001
        self.assertFalse(self.check()['valid'])

    def test_empty_success_series_rejects_phantom_points_and_nonzero_summary(self):
        events = [{'duration_ms': 500, 'outcome': 'failure'}]
        points = {'request_latency_ms': [500], 'successful_latency_ms': []}
        summary = {'request_latency_ms': {'avg': 500, 'p(95)': 500},
                   'successful_latency_ms': {'avg': 0, 'p(95)': 0}}
        self.assertEqual(pilot_records.latency_errors(events, points, summary), [])
        points['successful_latency_ms'] = [0]
        self.assertTrue(pilot_records.latency_errors(events, points, summary))
        points['successful_latency_ms'] = []
        summary['successful_latency_ms']['p(95)'] = 1
        self.assertTrue(pilot_records.latency_errors(events, points, summary))

    def test_latency_distributions_ignore_export_order_and_use_linear_percentiles(self):
        events = [{'duration_ms': value, 'outcome': 'success'} for value in (100, 900)]
        points = {name: [900, 100] for name in ('request_latency_ms', 'successful_latency_ms')}
        summary = {name: {'values': {'avg': 500, 'p(95)': 860}} for name in points}
        self.assertEqual(pilot_records.latency_errors(events, points, summary), [])
        summary['successful_latency_ms']['values']['p(95)'] = 900
        self.assertTrue(pilot_records.latency_errors(events, points, summary))

    def test_request_times_and_identity_are_checked(self):
        self.assertTrue(self.check()["valid"])
        for field, value, reason in (("run_id", "another", "request event has an unexpected schema, run or phase"),
                                     ("duration_ms", -5, "inconsistent request duration"),
                                     ("started_at_utc", "2026-10-18T12:00:02Z", "request identity changed: started_at_utc"),
                                     ("scenario_started_at_utc", "2026-10-18T12:00:02Z", "request identity changed: scenario_started_at_utc"),
                                     ("model_load_ms", -1, "invalid optional measurement: model_load_ms")):
            with self.subTest(field=field):
                self.events = [self.start, {**self.completed, field: value}]
                self.assertEqual(self.check()["errors"], [f"request evidence: {reason}"])

    def test_response_failure_is_valid_evidence_and_not_added_to_total_twice(self):
        self.completed.update(outcome="failure", http_status=503, error_category="http_status")
        self.remove_latency('successful_latency_ms')
        self.summary["metrics"]["inference_errors"] = {"passes": 1, "fails": 0}
        self.points[-1]["data"]["value"] = 1
        report = self.check()
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["counts"]["completed"], 1)
        self.assertEqual(report["counts"]["failed"], 1)

    def test_millisecond_boundaries_accept_one_tick_but_reject_two(self):
        beginning = records.timestamp(self.start["scenario_started_at_utc"])
        for offset_ms, valid in ((0, True), (-1, True), (-2, False), (1000, True), (1001, True), (1002, False)):
            with self.subTest(offset_ms=offset_ms):
                self.start["started_at_utc"] = records.iso_time(beginning + offset_ms / 1000)
                self.completed = {**self.completed, "started_at_utc": self.start["started_at_utc"],
                                  "finished_at_utc": records.iso_time(beginning + offset_ms / 1000 + .5)}
                self.events = [self.start, self.completed]
                report = self.check()
                self.assertEqual(report["valid"], valid, report)
                if not valid:
                    self.assertEqual(report["errors"], ["request start outside scheduled load interval"])
                elif offset_ms in (-1, 1001):
                    self.assertIn("request start within 1 ms timestamp boundary tolerance", report["warnings"])
                else:
                    self.assertEqual(report["warnings"], [])

    def test_observation_order_gaps_and_coverage_have_distinct_failures(self):
        cases = (((0, 3, 3, 5), "observation times are not strictly increasing"),
                 ((0, 4, 3, 5), "observation times are not strictly increasing"),
                 ((0, 15), "observation gap exceeds twice the configured interval"),
                 ((2, 5), "cluster observations do not bracket the load and drain interval"),
                 ((0, 1), "cluster observations do not bracket the load and drain interval"))
        for times, reason in cases:
            with self.subTest(times=times):
                self.samples = [sample(f"2026-10-18T12:00:{n:02d}Z") for n in (0, 3, 5)]
                self.assertTrue(self.check()["valid"])
                self.samples = [sample(f"2026-10-18T12:00:{n:02d}Z") for n in times]
                report = self.check()
                self.assertFalse(report["valid"])
                self.assertEqual(report["errors"], [reason])

    def test_missing_evidence_is_invalid(self):
        report = pilot_records.reconcile(self.folder, self.metadata)
        self.assertFalse(report["valid"])
        self.assertTrue(report["errors"])

    def test_truncated_or_nonobject_jsonl_is_invalid(self):
        self.assertTrue(self.check()["valid"])
        for tail in ('{"incomplete":', 'null\n', '[]\n'):
            with (self.folder / "request-events.jsonl").open("a") as output:
                output.write(tail)
            report = pilot_records.reconcile(self.folder, self.metadata)
            self.assertFalse(report["valid"])
            self.assertEqual(report["events_read"], {"started": 1, "completed": 1})
            self.assertTrue(self.check()["valid"])

    def test_launcher_errors_are_fatal_but_archive_problems_only_warn(self):
        self.metadata["errors"] = ["interrupted"]
        self.assertEqual(self.check()["errors"], ["launcher reported errors"])
        self.metadata["errors"] = []
        path = self.folder / "inputs" / "inference.js"
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    path.unlink()
                else:
                    path.write_text("changed")
                report = self.check()
                self.assertTrue(report["valid"], report)
                self.assertEqual(report["errors"], [])
                self.assertTrue(report["warnings"])

    def test_main_input_hashes_cover_helpers_analysis_and_missing_files(self):
        self.metadata['protocol_version'] = '1.1'
        self.metadata['deployment_snapshot'] = sample()['deployments']['items'][0]
        (self.folder / 'pod-logs').mkdir()
        (self.folder / 'pod-logs' / 'pod-1.log').write_text('')
        names = ('main_protocol.py', 'analyze.py', 'fixed_replicas.py')
        for name in names:
            raw = name.encode()
            (self.folder / 'inputs' / name).write_bytes(raw)
            self.metadata['source_sha256'][name] = hashlib.sha256(raw).hexdigest()
        report = self.check()
        self.assertTrue(report['valid'], report)
        self.assertEqual(report['warnings'], [])
        for name in names:
            with self.subTest(name=name):
                path = self.folder / 'inputs' / name
                path.write_bytes(b'changed')
                report = self.check()
                self.assertTrue(report['valid'], report)
                self.assertEqual(report['warnings'], [f'executable input changed: {name}'])
                path.write_bytes(name.encode())
        del self.metadata['source_sha256']['analyze.py']
        self.assertIn('incomplete executable input hashes', self.check()['warnings'])
        (self.folder / 'inputs' / 'main_protocol.py').unlink()
        self.assertTrue(any('main_protocol.py' in w for w in self.check()['warnings']))

    def test_optional_declared_hpa_hash_is_checked_without_changing_legacy_requirements(self):
        self.assertEqual(self.check()['warnings'], [])
        path = self.folder / 'inputs' / 'hpa.yaml'
        path.write_bytes(b'hpa manifest')
        self.metadata['source_sha256']['hpa.yaml'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(self.check()['warnings'], [])
        path.write_bytes(b'changed')
        report = self.check()
        self.assertTrue(report['valid'], report)
        self.assertEqual(report['warnings'], ['executable input changed: hpa.yaml'])

    def test_bad_warmup_or_abnormal_exit_is_rejected(self):
        self.assertTrue(self.check()["valid"])
        self.metadata["k6_exit_code"] = 1
        self.assertEqual(self.check()["errors"], ["load/collection processes did not finish normally"])
        self.metadata["k6_exit_code"] = 0
        (self.folder / "warmup.json").write_text(json.dumps({"phase": "warmup", "successful": False, "http_status": 503,
            "finished_at_utc": "2026-10-18T12:00:00.900Z"}))
        self.assertEqual(self.check()["errors"], ["warmup was not successful"])

    def test_cluster_errors_restart_and_hpa_are_rejected(self):
        broken = sample("2026-10-18T12:00:05Z")
        broken["pods"]["items"][0]["status"]["containerStatuses"][0]["restartCount"] = 1
        self.samples[1] = broken
        self.assertEqual(self.check()["errors"], ["pilot container identity or restart count changed"])
        reasons = {"error": "cluster collection contains errors", "hpa": "an HPA targets the pilot Deployment",
                   "not_ready": "pilot pod is not Ready", "two_pods": "pilot requires exactly one selected pod",
                   "missing_resource": "missing container resource counters",
                   "stale_deployment": "Deployment is not stable at one replica"}
        for change, reason in reasons.items():
            current = copy.deepcopy(sample())
            if change == "error":
                current["errors"] = [{"source": "kubelet", "message": "test error"}]
            elif change == "hpa":
                current["hpa"]["items"] = [{"spec": {"scaleTargetRef": {"kind": "Deployment", "name": "ollama"}}}]
            elif change == "not_ready":
                current["pods"]["items"][0]["status"]["conditions"][0]["status"] = "False"
            elif change == "two_pods":
                current["pods"]["items"] *= 2
            elif change == "missing_resource":
                current["resource_usage"] = []
            else:
                current["deployments"]["items"][0]["status"]["observedGeneration"] = 0
            with self.assertRaisesRegex(ValueError, reason):
                records.pilot_identity(current)


if __name__ == "__main__":
    unittest.main()

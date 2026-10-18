import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pilot_records


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


class RecordTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.metadata = {"run_id": "test", "duration_seconds": 1, "observer_interval_seconds": 5,
                         "initial_identity": pilot_records.pilot_identity(sample()),
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
        self.points = [{"type": "Point", "metric": k, "data": {"value": v}} for k, v in counts.items()]
        self.points.append({"type": "Point", "metric": "inference_errors", "data": {"value": 0}})
        self.samples = [sample(), sample("2026-10-18T12:00:05Z")]

    def check(self):
        write_lines(self.folder / "request-events.jsonl", self.events)
        write_lines(self.folder / "requests.json", self.points)
        write_lines(self.folder / "cluster.jsonl", self.samples)
        (self.folder / "summary.json").write_text(json.dumps(self.summary))
        return pilot_records.reconcile(self.folder, self.metadata)

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
        self.summary["metrics"]["inference_errors"] = {"passes": 1, "fails": 0}
        self.points[-1]["data"]["value"] = 1
        report = self.check()
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["counts"]["completed"], 1)
        self.assertEqual(report["counts"]["failed"], 1)

    def test_millisecond_boundaries_accept_one_tick_but_reject_two(self):
        beginning = pilot_records.timestamp(self.start["scenario_started_at_utc"])
        for offset_ms, valid in ((0, True), (-1, True), (-2, False), (1000, True), (1001, True), (1002, False)):
            with self.subTest(offset_ms=offset_ms):
                self.start["started_at_utc"] = pilot_records.iso_time(beginning + offset_ms / 1000)
                self.completed = {**self.completed, "started_at_utc": self.start["started_at_utc"],
                                  "finished_at_utc": pilot_records.iso_time(beginning + offset_ms / 1000 + .5)}
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
                pilot_records.pilot_identity(current)


if __name__ == "__main__":
    unittest.main()

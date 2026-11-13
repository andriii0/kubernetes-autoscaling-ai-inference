import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import custom_metric_run as run
import custom_metrics
import prepare_custom_metric as preparation
import run_pilot
from records import iso_time
from tests.bench.test_custom_metrics import NOW, pods, replies


def combined(parts):
    rows = []
    for name, part in zip(("source", "source_time", "health", "health_time"), parts):
        for row in part["data"]["result"]:
            rows.append({**row, "metric": {**row["metric"], "observation_field": name}})
    return {"status": "success", "data": {"resultType": "vector", "result": rows}}


class MonitorTests(unittest.TestCase):
    def test_cleanup_zeros_exclude_scrapes_within_clock_allowance(self):
        session = object.__new__(run.CustomSession)
        session.monitor = Mock()
        session.monitor.sample.side_effect = [
            {'source_at': NOW + .8, 'active_requests': 0},
            {'source_at': NOW + 2, 'active_requests': 0},
            {'source_at': NOW + 7, 'active_requests': 0}]
        with patch.object(run.time, 'time', return_value=NOW), patch.object(run.time, 'sleep'):
            result = session.zero()
        self.assertEqual(session.monitor.sample.call_count, 3)
        self.assertEqual(result['boundary'], NOW)
        self.assertEqual(result['after'], NOW + 1)
        self.assertTrue(result['successful'])

    def test_monitor_accepts_saved_clock_trigger_and_records_failed_clock_bounds(self):
        for offset, fails in ((.78, False), (1.5, True), (-1.5, True)):
            with self.subTest(offset=offset), tempfile.TemporaryDirectory() as temp:
                parts = replies(0)
                for part in parts[:4]:
                    part['data']['result'][0]['value'][0] = NOW + offset
                for index in (1, 3):
                    parts[index]['data']['result'][0]['value'][1] = str(NOW + offset - .1)
                source = combined(parts[:4])
                monitor = self.make_monitor(Path(temp), [source, parts[-1], source])
                with patch.object(run.time, 'time', return_value=NOW):
                    if fails:
                        with self.assertRaisesRegex(ValueError, 'clocks differ'):
                            monitor.sample()
                    else:
                        self.assertEqual(monitor.sample()['active_requests'], 0)
                monitor.close()
                record = json.loads((Path(temp) / 'custom-metric.jsonl').read_text())
                self.assertEqual('error' in record, fails)
                self.assertEqual(record['clock_contract'], 'bounded-clock-v2')
                self.assertEqual(record['brackets'][0]['before_sent_at'], NOW)
                self.assertEqual(record['brackets'][0]['before_received_at'], NOW)

    def make_monitor(self, folder, samples):
        monitor = run.Monitor(Mock(), folder)
        monitor.identity = custom_metrics.infrastructure_identity(pods())
        monitor.config = {}
        monitor.objects = Mock(return_value={"items": []})
        monitor.logs = Mock()
        monitor.observer.read.side_effect = [json.dumps(pods()), *[json.dumps(s) for s in samples]]
        return monitor

    def test_split_preserves_names_timestamps_and_duplicate_detection(self):
        data = replies()[:4]
        self.assertEqual(run.split_source(combined(data)), data)
        duplicate = combined(data)
        duplicate["data"]["result"].append(duplicate["data"]["result"][0])
        with self.assertRaisesRegex(ValueError, "exactly one"):
            run.split_source(duplicate)

    def test_bracket_pass_and_failed_mapping_are_saved(self):
        for wrong in (False, True):
            with self.subTest(wrong=wrong), tempfile.TemporaryDirectory() as temp:
                parts = replies()
                source = combined(parts[:4])
                if wrong:
                    parts[-1]["items"][0]["value"] = "100"
                monitor = self.make_monitor(Path(temp), [source, parts[-1], source])
                with patch.object(run.time, "time", return_value=NOW + 1):
                    if wrong:
                        with self.assertRaisesRegex(ValueError, "does not match"):
                            monitor.sample()
                    else:
                        self.assertEqual(monitor.sample()["active_requests"], 3)
                monitor.close()
                record = json.loads((Path(temp) / "custom-metric.jsonl").read_text())
                self.assertEqual("error" in record, wrong)
                self.assertEqual(len(record["brackets"]), 1)

    def test_scrape_crossing_is_recorded_and_retried_not_used_as_signal(self):
        with tempfile.TemporaryDirectory() as temp:
            earlier, later = replies(3), replies(2)
            later[1]["data"]["result"][0]["value"][1] = str(NOW - 1)
            later[3]["data"]["result"][0]["value"][1] = str(NOW - 1)
            a, b = combined(earlier[:4]), combined(later[:4])
            monitor = self.make_monitor(Path(temp), [a, earlier[-1], b, b, later[-1], b])
            with patch.object(run.time, "time", return_value=NOW + 1):
                self.assertEqual(monitor.sample()["active_requests"], 2)
            monitor.close()
            record = json.loads((Path(temp) / "custom-metric.jsonl").read_text())
            self.assertTrue(record["brackets"][0]["scrape_crossed_read"])
            self.assertEqual(len(record["brackets"]), 2)

    def test_stale_source_and_observation_gap_fail(self):
        for stale in (True, False):
            with self.subTest(stale=stale), tempfile.TemporaryDirectory() as temp:
                parts = replies()
                if stale:
                    parts[1]["data"]["result"][0]["value"][1] = str(NOW - 20)
                source = combined(parts[:4])
                monitor = self.make_monitor(Path(temp), [source, parts[-1], source])
                monitor.last_received = NOW - 20
                with patch.object(run.time, "time", return_value=NOW + 1), self.assertRaises(ValueError):
                    monitor.sample()
                monitor.close()

    def test_restart_configuration_change_and_log_failure_stop(self):
        for failure in ("restart", "config", "logs"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                monitor = self.make_monitor(Path(temp), [])
                if failure == "restart":
                    changed = pods()
                    changed["items"][0]["status"]["containerStatuses"][0]["restartCount"] = 1
                    monitor.observer.read.side_effect = [json.dumps(changed)]
                if failure == "config":
                    monitor.config = {"old": {}}
                if failure == "logs":
                    monitor.logs.update.side_effect = RuntimeError("stream ended")
                with self.assertRaises((ValueError, RuntimeError)):
                    monitor.sample()
                monitor.close()

    def test_crossed_scrape_does_not_hide_bad_adapter_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            earlier, later = replies(3), replies(2)
            earlier[-1]["items"][0]["value"] = "50"
            monitor = self.make_monitor(Path(temp), [combined(earlier[:4]), earlier[-1], combined(later[:4])])
            with patch.object(run.time, "time", return_value=NOW + 1), self.assertRaisesRegex(ValueError, "neither side"):
                monitor.sample()
            monitor.close()

    def test_raw_replay_rejects_changed_saved_signal_and_missing_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            identity = custom_metrics.infrastructure_identity(pods())
            run.save(folder / "custom-preflight.json", {"identity": identity})
            records = []
            for offset in (0, 5, 10):
                parts = replies(0)
                for part in parts[:4]:
                    part["data"]["result"][0]["value"][0] += offset
                for index in (1, 3):
                    parts[index]["data"]["result"][0]["value"][1] = str(NOW + offset - 3)
                parts[-1]["items"][0]["timestamp"] = iso_time(NOW + offset)
                source = combined(parts[:4])
                signal = custom_metrics.validate_signal(*parts, gateway_uid="gateway-uid", received_at=NOW + offset + 1)
                records.append({"pods": pods(), "brackets": [{"before": source, "adapter": parts[-1], "after": source}],
                                "signal": signal})
            def write():
                (folder / "custom-metric.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
            write()
            (folder / "gateway/pod-logs").mkdir(parents=True)
            run.save(folder / "gateway/log-coverage.json", {"gateway-uid": {"complete": True, "exit_code": 1,
                                                                          "stopped_by_collector": True}})
            row = {"request_id": "r:1", "method": "POST", "path": "/api/generate",
                   "upstream_cluster": "ollama", "attempts": "1"}
            (folder / "gateway/pod-logs/gateway-uid.log").write_text(iso_time(NOW + 3) + " " + json.dumps(row) + "\n")
            data = {"check": {"load_window": {"started_at_utc": iso_time(NOW + 2)}},
                    "metadata": {"duration_seconds": 8}, "events": [{"event": "started", "request_id": "r:1"}]}
            self.assertTrue(run.replay(folder, data)["valid"])
            records[1]["signal"]["active_requests"] = 10
            write()
            with self.assertRaisesRegex(ValueError, "differs"):
                run.replay(folder, data)
            records[1]["signal"]["active_requests"] = 0
            write()
            (folder / "gateway/pod-logs/gateway-uid.log").write_text("")
            with self.assertRaisesRegex(ValueError, "every client"):
                run.replay(folder, data)


class LifecycleTests(unittest.TestCase):
    def test_opt_in_and_archive_do_not_change_default_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "run"
            folder.mkdir()
            args, workload, seconds, prepared = run_pilot.parse_arguments(
                preparation.arguments(folder, 1, "http://localhost:1234"))
            meta = run_pilot.create_metadata(args, workload, seconds)
            inputs, _ = run_pilot.archive_inputs(args, meta, prepared)
            self.assertEqual(meta["purpose"], "custom-metric-preparation")
            self.assertNotIn("protocol_version", meta)
            self.assertTrue((inputs / "custom_metric_run.py").is_file())
            self.assertEqual(run_pilot.load_environment(args, "id")["GATEWAY_REQUEST_IDS"], "1")
            args.custom_metric_policy = None
            with patch.dict("os.environ", {"GATEWAY_REQUEST_IDS": "1"}):
                self.assertNotIn("GATEWAY_REQUEST_IDS", run_pilot.load_environment(args, "id"))

    def test_wrong_profile_or_frozen_protocol_is_rejected(self):
        for extra in (["--profile", "steady"], ["--protocol-version", "1.1"],
                      ["--observer-interval", "1"], ["--post-seconds", "0"], ["--mode", "fixed-1"]):
            with self.subTest(extra=extra), patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit):
                run_pilot.parse_arguments(preparation.arguments(Path("unused"), 1, "http://localhost:1") + extra)

    def test_cleanup_failure_does_not_run_quiet_gate_and_closes_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            session = object.__new__(run.CustomSession)
            session.folder = Path(temp)
            session.monitor = Mock()
            session.zero = Mock()
            with patch.object(run.Session, "restore", return_value={"successful": False, "errors": ["scale failed"]}):
                result = session.restore()
            self.assertFalse(result["successful"])
            session.zero.assert_not_called()
            session.monitor.close.assert_called_once()

    def test_cleanup_quiet_failure_is_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            session = object.__new__(run.CustomSession)
            session.folder, session.monitor = Path(temp), Mock()
            session.observer, session.container = Mock(), "ollama"
            with patch.object(run.Session, "restore", return_value={"successful": True, "errors": []}), \
                    patch("main_protocol.recover", side_effect=RuntimeError("backend still busy")):
                result = session.restore()
            self.assertFalse(result["successful"])
            self.assertIn("backend still busy", result["errors"])
            session.monitor.close.assert_called_once()

    def test_prepare_refuses_existing_hpa_before_backend_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            session = object.__new__(run.CustomSession)
            session.folder, session.observer = Path(temp), Mock()
            session.command = Mock(return_value='{"items":[{}]}')
            with patch.object(run, "Monitor"), patch.object(run.Session, "prepare") as parent:
                with self.assertRaisesRegex(ValueError, "pre-existing"):
                    session.prepare()
                parent.assert_not_called()


class QualificationTests(unittest.TestCase):
    def test_preliminary_metadata_gets_derived_version_without_raw_mutation(self):
        data = {"metadata": {"extension_version": "active-requests-preparation-v1"}}
        original = copy.deepcopy(data)
        with patch.object(preparation, "assessment", return_value={"overall": "fail"}) as assess:
            self.assertEqual(preparation.assess_preparation(data), {"overall": "fail"})
            self.assertEqual(assess.call_args.args[0]["metadata"]["protocol_version"],
                             "active-requests-preparation-v1")
        self.assertEqual(data, original)
        for meta in ({}, {"extension_version": "other"},
                     {"extension_version": "active-requests-preparation-v1", "protocol_version": "1.1"}):
            with self.assertRaises(ValueError):
                preparation.assess_preparation({"metadata": meta})

    def data(self):
        samples = []
        for at in range(-5, 427, 5):
            count = 1 if at < 151 else 2
            samples.append({"time": iso_time(NOW + at),
                            "hpa": {"items": [{"spec": {"scaleTargetRef": {"kind": "Deployment", "name": "ollama"}},
                                              "status": {"desiredReplicas": count}}]},
                            "pods": {"items": [{"metadata": {}, "status": {"conditions": [
                                {"type": "Ready", "status": "True"}]}} for _ in range(count)]}})
        return {"cluster": samples, "check": {"load_window": {"started_at_utc": iso_time(NOW)}}}

    def test_stability_and_growth_not_latency_choose_threshold(self):
        data = self.data()
        self.assertTrue(preparation.qualify(data)["qualifies"])
        data["cluster"][10]["hpa"]["items"][0]["status"]["desiredReplicas"] = 2
        self.assertFalse(preparation.qualify(data)["qualifies"])
        for selected, flags in ((1, (True, True)), (2, (False, True)), (None, (False, False))):
            self.assertEqual(preparation.select([{"target": n, "qualification": {"qualifies": flag}}
                                                 for n, flag in zip((1, 2), flags)]), selected)
        with self.assertRaises(ValueError):
            preparation.select([{"target": 1, "qualification": {"qualifies": True}}])

    def test_missing_or_gapped_replica_evidence_is_invalid(self):
        for mutate in (lambda d: d["cluster"].__delitem__(slice(10, 14)),
                       lambda d: d["cluster"].__delitem__(slice(-3, None)),
                       lambda d: d["cluster"][1]["hpa"]["items"][0]["status"].clear()):
            data = self.data()
            mutate(data)
            with self.assertRaises(ValueError):
                preparation.qualify(data)


if __name__ == "__main__":
    unittest.main()

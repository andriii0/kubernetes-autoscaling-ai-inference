import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import observe


def pod(uid="uid-1", restarts=0):
    return {"metadata": {"namespace": "inference", "name": "ollama-test", "uid": uid},
            "spec": {"nodeName": "ai-lab"},
            "status": {"containerStatuses": [{"name": "ollama", "restartCount": restarts,
                                                "state": {"running": {}}}]}}


def raw_metrics(counter=10, timestamp=10000, started=1):
    labels = '{container="ollama",namespace="inference",pod="ollama-test"}'
    return (f"container_cpu_usage_seconds_total{labels} {counter} {timestamp}\n"
            f"container_memory_working_set_bytes{labels} 1048576 {timestamp}\n"
            f"container_start_time_seconds{labels} {started} {timestamp}\n"
            f"node_cpu_usage_seconds_total 50 {timestamp}\n"
            f"node_memory_working_set_bytes 2097152 {timestamp}\n")


class ResourceTests(unittest.TestCase):
    def derive(self, raw, previous=None, item=None):
        return observe.derive_resource_usage(observe.parse_resource_metrics(raw),
            {("inference", "ollama-test"): item or pod()}, "ai-lab", 1, previous or {})

    def test_source_time_and_units(self):
        records, previous = self.derive(raw_metrics())
        self.assertIsNone(records[0]["cpu_cores"])
        records, _ = self.derive(raw_metrics(20, 15000), previous)
        self.assertEqual(records[0]["cpu_cores"], 2)
        self.assertEqual(records[0]["memory_working_set_bytes"], 1048576)
        self.assertEqual(records[0]["cpu_clock"], "source")

    def test_repeated_source_timestamp_is_not_zero_usage(self):
        _, previous = self.derive(raw_metrics())
        records, _ = self.derive(raw_metrics(), previous)
        self.assertIsNone(records[0]["cpu_cores"])

    def test_counter_reset_is_not_negative_cpu(self):
        _, previous = self.derive(raw_metrics())
        records, _ = self.derive(raw_metrics(1, 15000), previous)
        self.assertIsNone(records[0]["cpu_cores"])

    def test_restart_and_replacement_do_not_bridge_counters(self):
        _, previous = self.derive(raw_metrics())
        for item in (pod(restarts=1), pod(uid="uid-2")):
            records, _ = self.derive(raw_metrics(20, 15000), previous, item)
            self.assertIsNone(records[0]["cpu_cores"])

    def test_missing_memory_stays_missing(self):
        records, _ = self.derive(raw_metrics().replace(
            'container_memory_working_set_bytes{container="ollama",namespace="inference",pod="ollama-test"} 1048576 10000\n', ""))
        self.assertIsNone(records[0]["memory_working_set_bytes"])

    def test_unrelated_pods_are_excluded(self):
        records, _ = self.derive(raw_metrics().replace('pod="ollama-test"', 'pod="other"'))
        self.assertEqual([r["scope"] for r in records], ["node"])

    def test_parser_rejects_missing_and_nonfinite_metrics(self):
        for raw in ("# no measurements", "node_cpu_usage_seconds_total NaN",
                    'container_cpu_usage_seconds_total{broken} 1'):
            with self.assertRaises(ValueError):
                observe.parse_resource_metrics(raw)

    def test_prometheus_labels_and_optional_timestamps(self):
        records = observe.parse_resource_metrics(
            'container_cpu_usage_seconds_total{container="test\\\"name",pod="p",namespace="n"} 1e2\n')
        self.assertEqual(records[0]["labels"]["container"], 'test"name')
        self.assertEqual(records[0]["value"], 100)
        self.assertIsNone(records[0]["timestamp_ms"])


class ObserverTests(unittest.TestCase):
    def reader(self, *args):
        if "--raw" in args:
            return raw_metrics() if args[-1].endswith("/metrics/resource") else '{"items":[]}'
        return json.dumps({"items": [pod()] if "pods" in args else []})

    def test_empty_hpa_is_valid(self):
        collector = observe.Observer()
        with patch.object(collector, "read", side_effect=self.reader):
            sample = collector.collect(5)
        self.assertEqual(sample["errors"], [])
        self.assertEqual(sample["hpa"], {"items": []})
        self.assertEqual(len(sample["resource_usage"]), 2)

    def test_deployment_without_metadata_labels_is_collected(self):
        collector = observe.Observer()
        deployment = {"metadata": {"name": "ollama"}, "status": {"readyReplicas": 1},
                      "spec": {"selector": {"matchLabels": {"app": "ollama"}}}}
        def reader(*args):
            if "deployments" in args:
                self.assertNotIn("-l", args)
                return json.dumps({"items": [deployment]})
            return self.reader(*args)
        with patch.object(collector, "read", side_effect=reader):
            sample = collector.collect(5)
        self.assertEqual(sample["deployments"]["items"], [deployment])

    def test_source_failure_is_saved_and_does_not_hide_other_sources(self):
        collector = observe.Observer()
        def reader(*args):
            if args[-1].endswith("/metrics/resource"):
                raise subprocess.TimeoutExpired("kubectl", 5)
            return self.reader(*args)
        with patch.object(collector, "read", side_effect=reader), contextlib.redirect_stderr(io.StringIO()):
            sample = collector.collect(5)
        self.assertEqual(sample["errors"][0]["source"], "kubelet/ai-lab")
        self.assertIsNone(sample["kubelet"]["ai-lab"])
        self.assertIsNotNone(sample["pods"])
        self.assertEqual(collector.previous, {})

    def test_missing_container_metrics_are_reported(self):
        collector = observe.Observer()
        def reader(*args):
            if args[-1].endswith("/metrics/resource"):
                return "node_cpu_usage_seconds_total 10 1000\n"
            return self.reader(*args)
        with patch.object(collector, "read", side_effect=reader):
            sample = collector.collect(5)
        self.assertIn("Missing CPU/memory", sample["errors"][0]["message"])

    def test_failed_scrape_retains_raw_and_clears_counters(self):
        collector = observe.Observer()
        def reader(*args):
            if args[-1].endswith("/metrics/resource"):
                return raw_metrics() + "resource_scrape_error 1\n"
            return self.reader(*args)
        with patch.object(collector, "read", side_effect=self.reader):
            collector.collect(5)
        self.assertTrue(collector.previous)
        with patch.object(collector, "read", side_effect=reader), contextlib.redirect_stderr(io.StringIO()):
            sample = collector.collect(5)
        self.assertIn("resource_scrape_error", sample["errors"][0]["message"])
        self.assertIn("resource_scrape_error 1", sample["kubelet"]["ai-lab"]["raw"])
        self.assertEqual(sample["resource_usage"], [])
        self.assertEqual(collector.previous, {})

    def test_malformed_resource_payload_is_preserved(self):
        collector = observe.Observer()
        def reader(*args):
            return "bad response" if args[-1].endswith("/metrics/resource") else self.reader(*args)
        with patch.object(collector, "read", side_effect=reader), contextlib.redirect_stderr(io.StringIO()):
            sample = collector.collect(5)
        self.assertEqual(sample["kubelet"]["ai-lab"]["raw"], "bad response")
        self.assertIsNone(sample["kubelet"]["ai-lab"]["metrics"])
        self.assertTrue(sample["errors"])

    def test_existing_output_is_not_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.jsonl"
            path.write_text("original", encoding="utf-8")
            with patch.object(observe.Observer, "collect") as collect, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(observe.main([str(path), "--duration", "1"]), 2)
            self.assertEqual(path.read_text(encoding="utf-8"), "original")
            collect.assert_not_called()

    def test_cli_writes_failure_record_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failed.jsonl"
            with patch.object(observe.Observer, "read", side_effect=RuntimeError("offline")), \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(observe.main([str(path), "--duration", "0.01"]), 1)
            samples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(samples)
            for sample in samples:
                self.assertEqual(len(sample["errors"]), 5)
                self.assertIsNone(sample["resources"])
                self.assertEqual(sample["resource_usage"], [])


if __name__ == "__main__":
    unittest.main()

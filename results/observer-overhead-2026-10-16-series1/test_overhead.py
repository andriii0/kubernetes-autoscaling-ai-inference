import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("overhead", Path(__file__).with_name("analyze-overhead.py"))
overhead = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overhead)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        project = Path(self.temporary.name)
        (project / "bench").mkdir()
        self.root = project / "results" / "series"
        self.root.mkdir(parents=True)
        order = ["off", "on", "on", "off", "on", "off", "off", "on"]
        manifest = {"status": "complete", "order": order, "runs": [],
                    "observer_interval_seconds": 5, "mean_budget_percent": 10,
                    "p95_budget_percent": 10, "maximum_pair_mean_percent": 20}
        for name, key in (("observe.py", "observer_sha256"), ("inference.js", "load_script_sha256")):
            (project / "bench" / name).write_text("source", encoding="utf-8")
            manifest[key] = hashlib.sha256(b"source").hexdigest().upper()
        pod = {"kind": "Pod", "metadata": {"uid": "u", "labels": {"app": "ollama"}},
               "status": {"phase": "Running", "containerStatuses": [
                   {"name": "ollama", "restartCount": 0, "imageID": "image", "ready": True}]}}
        deployment = {"kind": "Deployment", "metadata": {"name": "ollama", "generation": 1},
                      "spec": {"replicas": 1}, "status": {"readyReplicas": 1}}
        for index, mode in enumerate(order, 1):
            directory = f"{index:02d}-{mode}"
            folder = self.root / directory
            folder.mkdir()
            begin = datetime(2026, 10, 16, index, tzinfo=timezone.utc)
            info = {"index": index, "pair": (index - 1) // 2 + 1, "mode": mode,
                    "directory": directory, "load_exit_code": 0, "cluster_unchanged": True,
                    "load_started_at_utc": begin.isoformat(),
                    "load_finished_at_utc": (begin + timedelta(seconds=120)).isoformat()}
            latency = 105 if mode == "on" else 100
            metrics = {"iterations": {"count": 24}, "inference_errors": {"value": 0},
                       "dropped_iterations": {"count": 0},
                       "successful_latency_ms": {"avg": latency, "p(95)": latency}}
            events = [{"type": "Point", "metric": name, "data": {"value": value}}
                      for _ in range(24) for name, value in (
                          ("successful_latency_ms", latency), ("inference_errors", 0), ("output_tokens", 56))]
            for name in ("cluster-before.json", "cluster-after.json"):
                self.write(directory + "/" + name, {"items": [pod, deployment]})
            self.write(directory + "/summary.json", {"metrics": metrics})
            (folder / "requests.json").write_text("\n".join(json.dumps(p) for p in events), encoding="utf-8")
            if mode == "on":
                info["observer_exit_code"] = 0
                observations = [{"time": (begin + timedelta(seconds=offset)).isoformat(),
                                 "pods": {"items": [pod]}, "hpa": {"items": []}, "errors": []}
                                for offset in range(-10, 140, 5)]
                (folder / "cluster.jsonl").write_text("\n".join(json.dumps(o) for o in observations), encoding="utf-8")
            self.write(directory + "/metadata.json", info)
            manifest["runs"].append(info)
        self.write("manifest.json", manifest)

    def write(self, name, data):
        (self.root / name).write_text(json.dumps(data), encoding="utf-8")

    def test_valid_series_uses_pairs_and_raw_samples(self):
        result = overhead.analyze(self.root)
        self.assertEqual(result["total_requests"], 192)
        self.assertAlmostEqual(result["median_paired_mean_change_percent"], 5)
        self.assertAlmostEqual(result["median_paired_p95_change_percent"], 5)
        self.assertTrue(result["provisional_budget_met"])
        self.assertEqual(len(result["pairs"]), 4)

    def test_incomplete_series_is_rejected(self):
        manifest = overhead.read_json(self.root / "manifest.json")
        manifest["status"] = "running"
        self.write("manifest.json", manifest)
        with self.assertRaisesRegex(AssertionError, "Incomplete"):
            overhead.analyze(self.root)

    def test_cluster_restart_is_rejected(self):
        snapshot = overhead.read_json(self.root / "03-on/cluster-after.json")
        snapshot["items"][0]["status"]["containerStatuses"][0]["restartCount"] = 1
        self.write("03-on/cluster-after.json", snapshot)
        with self.assertRaisesRegex(AssertionError, "Cluster changed"):
            overhead.analyze(self.root)

    def test_observer_gap_is_rejected(self):
        path = self.root / "02-on/cluster.jsonl"
        rows = path.read_text(encoding="utf-8").splitlines()
        row = json.loads(rows[0])
        row["errors"] = [{"source": "kubelet", "message": "timeout"}]
        rows[0] = json.dumps(row)
        path.write_text("\n".join(rows), encoding="utf-8")
        with self.assertRaises(AssertionError):
            overhead.analyze(self.root)

    def test_false_summary_is_rejected(self):
        summary = overhead.read_json(self.root / "01-off/summary.json")
        summary["metrics"]["successful_latency_ms"]["avg"] = 999
        self.write("01-off/summary.json", summary)
        with self.assertRaises(AssertionError):
            overhead.analyze(self.root)

    def observations(self):
        path = self.root / "02-on/cluster.jsonl"
        return path, [json.loads(line) for line in path.read_text().splitlines()]

    def write_observations(self, path, rows):
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    def test_repeated_internal_collection_times_are_rejected(self):
        path, rows = self.observations()
        for row in rows[1:-1]:
            row["time"] = rows[1]["time"]
        self.write_observations(path, rows)
        with self.assertRaisesRegex(AssertionError, "strictly increasing"):
            overhead.analyze(self.root)

    def test_reordered_collection_times_are_rejected(self):
        path, rows = self.observations()
        rows[3], rows[4] = rows[4], rows[3]
        self.write_observations(path, rows)
        with self.assertRaisesRegex(AssertionError, "strictly increasing"):
            overhead.analyze(self.root)

    def test_internal_gap_is_rejected_even_when_count_and_endpoints_pass(self):
        path, rows = self.observations()
        del rows[5:7]
        self.assertEqual(len(rows), 28)
        self.write_observations(path, rows)
        with self.assertRaisesRegex(AssertionError, "collection gap"):
            overhead.analyze(self.root)

    def test_small_collection_jitter_is_valid(self):
        path, rows = self.observations()
        rows[5]["time"] = (datetime.fromisoformat(rows[5]["time"]) + timedelta(seconds=.25)).isoformat()
        self.write_observations(path, rows)
        self.assertTrue(overhead.analyze(self.root)["provisional_budget_met"])

    def test_verified_frozen_sources_allow_later_code_changes(self):
        project = self.root.parents[1]
        frozen = self.root / "sources"
        frozen.mkdir()
        for name in ("inference.js", "observe.py"):
            (frozen / name).write_bytes((project / "bench" / name).read_bytes())
            (project / "bench" / name).write_text("later revision", encoding="utf-8")
        self.assertTrue(overhead.analyze(self.root)["source_hashes_match"])
        (frozen / "inference.js").write_text("corrupted snapshot", encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "Source changed"):
            overhead.analyze(self.root)


if __name__ == "__main__":
    unittest.main()

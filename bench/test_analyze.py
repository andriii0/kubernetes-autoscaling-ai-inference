import csv
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import analyze
import test_pilot_records as fixtures


class AnalysisTests(unittest.TestCase):
    def data(self):
        fixture = fixtures.RecordTests("test_valid_collection_and_missing_optional_values")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.metadata["namespace"] = "inference"
        fixture.metadata["rate"] = 2
        fixture.samples = []
        for second, cpu, memory in ((0, 9, 99), (1, 1, 2), (2, 2, 4), (5, 9, 99)):
            point = fixtures.sample(f"2026-10-18T12:00:{second:02d}Z")
            point["resource_usage"][0].update(namespace="inference", cpu_cores=cpu,
                cpu_timestamp_ms=analyze.timestamp(point["time"]) * 1000,
                memory_timestamp_ms=analyze.timestamp(point["time"]) * 1000,
                memory_working_set_bytes=memory * 2**20)
            fixture.samples.append(point)
        fixture.check()
        (fixture.folder / "metadata.json").write_text(json.dumps(fixture.metadata))
        return analyze.load_results(fixture.folder)

    def test_known_counts_latency_and_measured_window_resources(self):
        row = analyze.calculate_metrics(self.data())
        self.assertTrue(row["collection_valid"])
        self.assertEqual((row["started"], row["completed"], row["successful"], row["failed"]), (1, 1, 1, 0))
        self.assertEqual((row["mean_ms"], row["p50_ms"], row["p95_ms"]), (500, 500, 500))
        self.assertEqual(row["cpu_mean_cores"], 1.5)
        self.assertEqual(row["peak_memory_mib"], 4)
        self.assertEqual(row["observations_in_load"], 2)
        self.assertEqual(row["token_samples"], 0)
        self.assertIsNone(row["tokens_min"])
        self.assertAlmostEqual(analyze.percentile([1, 2, 3, 4, 5], .95), 4.8)

    def test_zero_tokens_and_missing_resources_are_distinct(self):
        data = self.data()
        data["events"][1]["output_tokens"] = 0
        for sample in data["cluster"]:
            sample["resource_usage"][0].update(cpu_cores=None, memory_working_set_bytes=None)
        row = analyze.calculate_metrics(data)
        self.assertEqual(row["token_samples"], 1)
        self.assertEqual(row["tokens_min"], 0)
        self.assertIsNone(row["cpu_mean_cores"])
        self.assertIsNone(row["peak_memory_mib"])

    def test_saved_live_check_agrees_with_independent_k6_summary(self):
        folder = Path(__file__).resolve().parents[1] / "results/pilot/20261018T202951240Z-collection-check"
        row = analyze.calculate_metrics(analyze.load_results(folder))
        summary = json.loads((folder / "summary.json").read_text())["metrics"]
        self.assertEqual(row["completed"], summary["http_reqs"]["count"])
        self.assertAlmostEqual(row["mean_ms"], summary["successful_latency_ms"]["avg"])
        self.assertAlmostEqual(row["p95_ms"], summary["successful_latency_ms"]["p(95)"])

    def test_existing_output_is_rejected_without_touching_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            sentinel = folder / "old.txt"
            sentinel.write_bytes(b"saved analysis")
            with self.assertRaises(SystemExit) as result:
                analyze.main(["missing-run", "--output-dir", str(folder)])
            self.assertEqual(result.exception.code, 2)
            self.assertEqual(sentinel.read_bytes(), b"saved analysis")

    def test_csv_is_generated_without_changing_raw_events(self):
        data = self.data()
        source = data["folder"] / "request-events.jsonl"
        before = source.read_bytes()
        output = data["folder"] / "analysis"
        self.assertEqual(analyze.main([str(data["folder"]), "--output-dir", str(output), "--no-plots"]), 0)
        self.assertEqual(source.read_bytes(), before)
        with (output / "summary.csv").open(newline="") as file:
            row = list(csv.DictReader(file))[0]
        self.assertEqual(row["p95_ms"], "500.0")
        self.assertEqual(row["tokens_min"], "")
        self.assertFalse(list(output.glob("*.png")))

    @unittest.skipUnless(importlib.util.find_spec('matplotlib'), 'Install the optional analysis dependency for plot checks')
    def test_plots_are_generated_without_changing_raw_events(self):
        data = self.data()
        source = data['folder'] / 'request-events.jsonl'
        before = source.read_bytes()
        output = data['folder'] / 'plots'
        self.assertEqual(analyze.main([str(data['folder']), '--output-dir', str(output)]), 0)
        self.assertEqual(source.read_bytes(), before)
        png = next(output.glob("*.png"))
        self.assertTrue(png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn("Container CPU", next(output.glob("*.svg")).read_text())

    def test_missing_plot_dependency_has_actionable_error_and_no_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'analysis'
            message = io.StringIO()
            with patch.dict(sys.modules, {'matplotlib': None}), redirect_stderr(message):
                self.assertEqual(analyze.main(['unused-source', '--output-dir', str(output)]), 1)
            self.assertIn('--no-plots', message.getvalue())
            self.assertIn('Matplotlib', message.getvalue())
            self.assertFalse(output.exists())

    @unittest.skipUnless(importlib.util.find_spec('matplotlib'), 'Install the optional analysis dependency for plot checks')
    def test_saved_fixed_and_autoscaling_plots_keep_replica_and_hpa_series(self):
        root = Path(__file__).resolve().parents[1]
        runs = [('results/fixed-replicas/check-2026-10-20-series1/peak-1', 'CPU per copy'),
                ('results/autoscaling/check-2026-10-20-series1/burst-1', 'HPA desired')]
        with tempfile.TemporaryDirectory() as temporary:
            for index, (run, label) in enumerate(runs):
                with self.subTest(run=run):
                    data = analyze.load_results(root / run)
                    destination = Path(temporary) / str(index)
                    analyze.create_plots(data, analyze.calculate_metrics(data), destination)
                    self.assertTrue(destination.with_suffix('.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
                    self.assertIn(label, destination.with_suffix('.svg').read_text())

    def test_invalid_collection_stays_explicit(self):
        data = self.data()
        data["metadata"]["errors"] = ["interrupted"]
        (data["folder"] / "metadata.json").write_text(json.dumps(data["metadata"]))
        row = analyze.calculate_metrics(analyze.load_results(data["folder"]))
        self.assertFalse(row["collection_valid"])
        self.assertEqual(row["collection_error_details"], "launcher reported errors")


if __name__ == "__main__":
    unittest.main()

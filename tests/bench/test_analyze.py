import csv
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import analyze
import summarize_main
from tests.bench import fixtures


class AnalysisTests(unittest.TestCase):
    def data(self):
        fixture = fixtures.RunFixture()
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

    def autoscaling_fixture(self):
        fixture = fixtures.autoscaling_fixture(self)
        fixture.metadata.update(rate=2, low_rate=2, phases=[],
                                burst_stages=[{'name': 'low', 'seconds': 1, 'target': 'low'}])
        (fixture.folder / 'metadata.json').write_text(json.dumps(fixture.metadata))
        self.assertTrue(fixture.check()['valid'])
        return fixture

    def test_missing_autoscaling_sources_keep_invalid_rows_and_explicit_gaps(self):
        valid = self.autoscaling_fixture()
        for missing in (('pods',), ('hpa',), ('pods', 'hpa')):
            with self.subTest(missing=missing):
                broken = self.autoscaling_fixture()
                point = fixtures.sample('2026-10-18T12:00:01.500Z')
                for key in missing:
                    point[key] = None
                    point['errors'].append({'source': key, 'message': 'simulated API timeout'})
                broken.samples.insert(1, point)
                self.assertFalse(broken.check()['valid'])
                data = analyze.load_results(broken.folder)
                detail = analyze.scaling_details(data)
                gap = detail['timeline'][1]
                if 'pods' in missing:
                    for field in ('ready', 'running', 'terminating'):
                        self.assertIsNone(gap[field])
                    self.assertIsNone(analyze.resource_points(data)[1]['ready'])
                    self.assertIsNone(detail['pods']['pod-1']['first_absent_at_utc'])
                    self.assertFalse(data['check']['logs']['complete'])
                if 'hpa' in missing:
                    self.assertIsNone(gap['desired'])
                output = broken.folder / 'analysis'
                self.assertEqual(analyze.main([str(valid.folder), str(broken.folder),
                                               '--output-dir', str(output), '--no-plots']), 0)
                rows = json.loads((output / 'analysis.json').read_text())
                self.assertEqual([r['collection_valid'] for r in rows], [True, False])
                self.assertTrue(rows[1]['collection_error_details'])
                saved = json.loads((output / 'scaling.json').read_text())[broken.folder.name]
                self.assertEqual(saved['timeline'][1], gap)

    def test_all_pod_snapshots_missing_are_not_zero_replicas(self):
        broken = self.autoscaling_fixture()
        for sample in broken.samples:
            sample['pods'] = None
            sample['errors'] = [{'source': 'pods', 'message': 'simulated API timeout'}]
        self.assertFalse(broken.check()['valid'])
        output = broken.folder / 'analysis'
        self.assertEqual(analyze.main([str(broken.folder), '--output-dir', str(output), '--no-plots']), 0)
        timeline = json.loads((output / 'scaling.json').read_text())[broken.folder.name]['timeline']
        self.assertTrue(all(p['ready'] is None and p['running'] is None for p in timeline))
        self.assertFalse(json.loads((output / 'analysis.json').read_text())[0]['collection_valid'])

    @unittest.skipUnless(importlib.util.find_spec('matplotlib'), 'Install the optional analysis dependency for plot checks')
    def test_missing_autoscaling_pods_still_produce_plots(self):
        broken = self.autoscaling_fixture()
        broken.samples[0]['pods'] = None
        broken.samples[0]['errors'] = [{'source': 'pods', 'message': 'simulated API timeout'}]
        self.assertFalse(broken.check()['valid'])
        output = broken.folder / 'plots'
        self.assertEqual(analyze.main([str(broken.folder), '--output-dir', str(output)]), 0)
        self.assertTrue(next(output.glob('*.png')).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertFalse(json.loads((output / 'analysis.json').read_text())[0]['collection_valid'])

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
        folder = fixtures.ROOT / "results/pilot/20261018T202951240Z-collection-check"
        row = analyze.calculate_metrics(analyze.load_results(folder))
        summary = json.loads((folder / "summary.json").read_text())["metrics"]
        self.assertEqual(row["completed"], summary["http_reqs"]["count"])
        self.assertAlmostEqual(row["mean_ms"], summary["successful_latency_ms"]["avg"])
        self.assertAlmostEqual(row["p95_ms"], summary["successful_latency_ms"]["p(95)"])

    def test_duplicate_run_folder_names_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.data()['folder']
            second = root / 'other-series' / first.name
            shutil.copytree(first, second)
            output = root / 'analysis'
            message = io.StringIO()
            with redirect_stderr(message):
                self.assertEqual(analyze.main([str(first), str(second),
                                               '--output-dir', str(output), '--no-plots']), 1)
            self.assertIn(f'duplicate run folder name {first.name!r}', message.getvalue())
            self.assertFalse(output.exists())

    def test_main_optional_measurements_keep_missing_values_and_zero_distinct(self):
        events = [{'output_tokens': 56, 'model_load_ms': None},
                  {'output_tokens': None, 'model_load_ms': None},
                  {'output_tokens': 0}]
        summary = summarize_main.optional_measurements(events)
        self.assertEqual(json.loads(summary['output_token_counts']), {'56': 1, 'null': 1, '0': 1})
        self.assertIsNone(summary['largest_model_load_ms'])
        events[-1]['model_load_ms'] = 0
        self.assertEqual(summarize_main.optional_measurements(events)['largest_model_load_ms'], 0)

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
        root = fixtures.ROOT
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

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze_custom_comparison as analysis
import prepare_custom_metric as prep
import run_custom_comparison as driver
import run_pilot
from records import iso_time


class ComparisonTests(unittest.TestCase):
    def test_exact_matrix_and_explicit_metadata(self):
        self.assertEqual([c['policy'] for c in driver.CELLS],
                         ['cpu', 'active-1', 'active-1', 'cpu', 'cpu', 'active-1'])
        for cell in driver.CELLS:
            args, workload, seconds, prepared = run_pilot.parse_arguments(
                driver.arguments(Path('unused'), cell['policy'], 'http://localhost:1'))
            meta = run_pilot.create_metadata(args, workload, seconds)
            self.assertTrue(prepared)
            self.assertEqual(seconds, 782)
            self.assertEqual(meta['extension_version'], 'active-requests-comparison-v2')
            self.assertEqual(meta['purpose'], 'custom-metric-comparison')
            self.assertNotIn('protocol_version', meta)
        with patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit):
            run_pilot.parse_arguments(prep.arguments(Path('unused'), 2, 'http://localhost:1') + ['--custom-metric-comparison'])

    def test_capacity_excludes_gaps_and_missing_values_and_clips(self):
        points = [{'time': t, 'desired': v} for t, v in [(0, 1), (5, 2), (10, None), (15, 3), (30, 1)]]
        result = analysis.capacity(points, 2, 28, 'desired')
        self.assertEqual(result['covered_seconds'], 8)
        self.assertEqual(result['replica_seconds'], 13)
        self.assertEqual(result['missing_seconds'], 18)

    def test_collector_boundary_requires_exact_verified_hashes(self):
        before = {'custom_metrics.py': 'old', 'run_pilot.py': 'old-launcher'}
        after = {'custom_metrics.py': 'new', 'run_pilot.py': 'new-launcher'}
        record = {'status': 'verified', 'clock_contract': 'bounded-clock-v2',
                  'changes': {'custom_metrics.py': {'prepared': 'old', 'comparison': 'new'}}}
        self.assertEqual(driver.source_boundary(before, after, record)['changes']['custom_metrics.py'],
                         record['changes']['custom_metrics.py'])
        for invalid in (None, {**record, 'status': 'unverified'}, {**record, 'changes': {}}):
            with self.assertRaisesRegex(ValueError, 'exact verified'):
                driver.source_boundary(before, after, invalid)
        with self.assertRaisesRegex(ValueError, 'unreviewed'):
            driver.source_boundary({**before, 'workload.json': 'old'}, {**after, 'workload.json': 'new'}, record)

    def test_on_time_denominator_includes_failure_unfinished_and_late_success(self):
        start = 1700000000
        events = [{'event': 'started', 'request_id': str(i), 'started_at_utc': iso_time(start + t)}
                  for i, t in enumerate((121, 122, 123, 124, 421))]
        events += [{'event': 'completed', 'request_id': str(i), 'outcome': outcome, 'duration_ms': ms}
                   for i, outcome, ms in ((0, 'success', 5000), (1, 'success', 5001), (2, 'failure', 30000))]
        data = {'metadata': {'phases': [{'phase': 'post_load_no_new_requests', 'started_at_utc': iso_time(start+782)}],
                             'post_seconds': 300}, 'events': events, 'cluster': [],
                'check': {'load_window': {'started_at_utc': iso_time(start)}, 'counts': {'dropped': 2}}}
        result = analysis.outcomes(data, Path('unused'), 'cpu')
        self.assertEqual(result['peak_started'], 4)
        self.assertEqual(result['peak_on_time_fraction'], .25)
        self.assertEqual(result['peak_error_fraction'], .25)
        self.assertEqual(result['peak_unfinished'], 1)
        self.assertEqual(result['dropped_starts'], 2)
        self.assertEqual(result['capacity']['load']['ready']['missing_seconds'], 782)
        self.assertIsNone(result['reaction']['2']['ready_at_seconds_from_peak'])

    def rows(self):
        return [{**cell, 'outcomes': {'peak_on_time_fraction': .8 if cell['policy']=='active-1' else .5,
                                      'peak_error_fraction': 0},
                 'assessment': {'primary': {'p95_ms': 1000}}} for cell in driver.CELLS]

    def test_summary_requires_all_pairs_and_consistent_improvement(self):
        rows = self.rows()
        self.assertTrue(analysis.summarize(rows)['consistent_service_improvement'])
        rows[-1]['outcomes']['peak_error_fraction'] = .01
        self.assertFalse(analysis.summarize(rows)['consistent_service_improvement'])
        rows[-1]['outcomes']['peak_error_fraction'] = 0
        rows[-1]['outcomes']['peak_on_time_fraction'] = .5
        self.assertFalse(analysis.summarize(rows)['consistent_service_improvement'])
        with self.assertRaises(ValueError):
            analysis.summarize(rows[:-1])

    def test_failed_review_stops_before_second_cell_and_keeps_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'series'
            from contextlib import nullcontext
            with patch.object(driver, 'preparation_evidence', return_value={}), \
                 patch.object(driver, 'render'), patch.object(driver, 'source_hashes', return_value={}), \
                 patch.object(driver, 'read', return_value={'source_sha256': {}}), \
                 patch.object(driver, 'live_preflight', return_value={'host': {}}), \
                 patch.object(driver, 'gateway_url', return_value=nullcontext('http://localhost:1')), \
                 patch.object(driver, 'run_command', return_value=1) as launch, \
                 patch.object(driver, 'review', side_effect=ValueError('cleanup failed')):
                code = driver.main(['--output-dir', str(out), '--preparation-dir', str(temp), '--execute'])
            self.assertEqual(code, 1)
            launch.assert_called_once()
            manifest = json.loads((out / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'stopped')
            self.assertEqual(manifest['completed'], [])
            self.assertIn('cleanup failed', manifest['errors'])

    def test_comparison_assessment_branch_does_not_require_preparation_qualification(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            check = {'valid': True, 'warnings': [], 'errors': []}
            (folder / 'collection-check.json').write_text(json.dumps(check))
            data = {'metadata': {'exit_code': 99, 'collection_valid': True, 'errors': [], 'warnings': [],
                    'recovery': {'successful': True}, 'gateway_check': {'complete': True}, 'source_sha256': {},
                    'custom_bundle': {'sha256': {}}, 'extension_version': 'active-requests-comparison-v1',
                    'purpose': 'custom-metric-comparison'}, 'check': check}
            assessment = {'data_valid': True, 'duration_complete': True, 'dropped': 0, 'unfinished': 0, 'overall': 'fail'}
            with patch.object(prep, 'load_results', return_value=data), \
                 patch.object(prep, 'assessment', return_value=assessment), patch.object(prep, 'phase_results', return_value=[]), \
                 patch('custom_metric_run.replay', return_value={'valid': True}), patch.object(prep, 'qualify') as qualify:
                self.assertEqual(prep.review(folder, 99, comparison=True)['assessment']['overall'], 'fail')
                qualify.assert_not_called()

    def test_complete_driver_runs_six_cells_retains_service_misses(self):
        with tempfile.TemporaryDirectory() as temp:
            from contextlib import nullcontext
            out = Path(temp) / 'series'
            meta = {'source_sha256': {}, 'initial_identity': {'image_id': 'image'},
                    'duration_seconds': 782, 'rate': 12, 'low_rate': 2, 'post_seconds': 300}
            def read(path):
                policy = next((c['policy'] for c in driver.CELLS
                               if f"attempt-{c['order']:02d}-{c['policy']}" in str(path)), 'cpu')
                return {**meta, 'custom_metric_policy': policy}
            def analyze(args):
                Path(args[args.index('--output-dir') + 1]).mkdir()
                return 0
            outcome = {'peak_on_time_fraction': .5, 'peak_error_fraction': 0}
            with patch.object(driver, 'preparation_evidence', return_value={}), \
                 patch.object(driver, 'render'), patch.object(driver, 'source_hashes', return_value={}), \
                 patch.object(driver, 'read', side_effect=read), \
                 patch.object(driver, 'live_preflight', return_value={'host': {}}), \
                 patch.object(driver, 'gateway_url', return_value=nullcontext('http://localhost:1')), \
                 patch.object(driver, 'run_command', return_value=99) as launch, \
                 patch.object(driver, 'review', side_effect=lambda *a, **k: {'assessment': {'overall': 'fail', 'primary': {'p95_ms': 7000}}}), \
                 patch.object(driver, 'load_results', return_value={}), \
                 patch.object(driver, 'outcomes', return_value=outcome), \
                 patch.object(driver, 'primary_resources', return_value={}), \
                 patch.object(driver, 'analyze', side_effect=analyze):
                self.assertEqual(driver.main(['--output-dir', str(out), '--preparation-dir', str(temp), '--execute']), 0)
            self.assertEqual(launch.call_count, 6)
            manifest = json.loads((out / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'finished')
            self.assertEqual(len(manifest['completed']), 6)
            self.assertFalse(json.loads((out / 'comparison-summary.json').read_text())['consistent_service_improvement'])


if __name__ == '__main__':
    unittest.main()

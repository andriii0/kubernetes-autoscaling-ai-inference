import json
from pathlib import Path
import tempfile
import unittest

from lab.results import Results


class ResultTests(unittest.TestCase):
    def test_custom_metrics_group_retains_comparison_assessment(self):
        folder = self.root / 'custom-metric/comparison-example/attempt-01-cpu'
        folder.mkdir(parents=True)
        (folder / 'metadata.json').write_text(json.dumps(self.metadata))
        assessment = {'overall': 'fail', 'data_valid': True, 'primary': {'name': 'peak', 'p95_ms': 7000}}
        (folder.parent / 'manifest.json').write_text(json.dumps({
            'protocol': 'active-requests-comparison-v3', 'cells': [1] * 6,
            'completed': [{'run': folder.name, 'assessment': assessment}]}))
        run = self.results.detail(folder.relative_to(self.root).as_posix())
        self.assertEqual((run['group'], run['p95_scope'], run['p95_ms']), ('Custom metrics', 'Peak', 7000))
        self.assertEqual(run['status'], 'Target missed')
        series = self.results.detail(folder.parent.relative_to(self.root).as_posix())
        self.assertEqual((series['name'], series['total']), ('CPU vs requests', 6))

    def test_custom_completion_keeps_superseded_failures_visible(self):
        series = self.root / 'custom-metric/comparison-resumed'
        series.mkdir(parents=True)
        completed = []
        policies = ('cpu', 'active-1', 'active-1', 'cpu', 'cpu', 'active-1')
        for order, policy in enumerate(policies, 1):
            name = f'attempt-{order:02d}-{policy}' + ('-retry-01' if order == 5 else '')
            folder = series / name
            folder.mkdir()
            (folder / 'metadata.json').write_text(json.dumps(self.metadata))
            (folder / 'collection-check.json').write_text(json.dumps({'valid': True}))
            completed.append({'run': name, 'assessment': {'overall': 'pass', 'data_valid': True}})
        failed = series / 'attempt-05-cpu'
        failed.mkdir()
        (failed / 'metadata.json').write_text(json.dumps({**self.metadata, 'exit_code': 1, 'collection_valid': False}))
        manifest = {'protocol': 'active-requests-comparison-v3', 'status': 'finished',
                    'cells': list(policies), 'completed': completed}
        (series / 'manifest.json').write_text(json.dumps(manifest))
        result = next(r for r in self.results.catalog() if r['id'] == 'custom-metric/comparison-resumed')
        self.assertEqual((result['status'], result['completed'], result['total']), ('Complete', 6, 6))
        self.assertEqual(result['preserved_originals'], 1)
        self.assertIn('custom-metric/comparison-resumed/attempt-05-cpu', result['attempts'])
        # A failed cell without an accepted replacement must still affect the status.
        manifest['completed'] = completed[:4]
        (series / 'manifest.json').write_text(json.dumps(manifest))
        (series / completed[4]['run'] / 'metadata.json').write_text(json.dumps({**self.metadata, 'exit_code': 1}))
        result = next(r for r in self.results.catalog() if r['id'] == 'custom-metric/comparison-resumed')
        self.assertEqual(result['status'], 'Needs review')
        self.assertEqual(result['preserved_originals'], 0)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.results = Results(self.root)
        self.folder = self.root / 'main/series/attempt-01-autoscaling-burst'
        self.folder.mkdir(parents=True)
        self.metadata = dict(mode='autoscaling', profile='burst', protocol_version='1.1', rate=8, low_rate=2,
                             started_at_utc='2026-10-25T12:00:00Z', finished_at_utc='2026-10-25T12:20:00Z',
                             exit_code=0, collector_exit_code=0, collection_valid=True,
                             workload={'main_protocol': {'primary_p95_ms': 5000}})
        self.write('metadata.json', self.metadata)
        self.write('collection-check.json', {'valid': True, 'counts': {'completed': 2, 'successful': 1, 'failed': 1}})
        self.write('summary.json', {'metrics': {'successful_latency_ms': {'p(95)': 2705.75}}})
        self.write('assessment.json', {'data_valid': True, 'overall': 'fail', 'primary': {'name': 'peak', 'p95_ms': 6000}})

    def write(self, name, data):
        (self.folder / name).write_text(json.dumps(data), encoding='utf-8')

    def detail(self):
        return self.results.detail(self.folder.relative_to(self.root).as_posix())

    def test_primary_scope_and_target_miss_are_separate_from_collection(self):
        data = self.detail()
        self.assertEqual((data['p95_ms'], data['p95_scope'], data['target_ms']), (6000, 'Peak', 5000))
        self.assertEqual((data['status'], data['tone'], data['collection_valid']), ('Target missed', 'warn', True))
        self.assertEqual((data['successful'], data['failed'], data['timeouts']), (1, 1, None))

    def test_absent_primary_never_uses_whole_run_latency(self):
        (self.folder / 'assessment.json').unlink()
        data = self.detail()
        self.assertIsNone(data['p95_ms'])
        self.assertEqual(data['p95_scope'], 'Peak')

    def test_pilot_whole_run_and_unknown_measurements(self):
        self.metadata.pop('protocol_version')
        self.write('metadata.json', self.metadata)
        (self.folder / 'assessment.json').unlink()
        (self.folder / 'collection-check.json').unlink()
        data = self.detail()
        self.assertEqual((data['p95_ms'], data['p95_scope']), (2705.75, 'Whole run'))
        self.assertIsNone(data['failed'])
        self.assertIsNone(data['successful'])
        self.assertIsNone(data['timeouts'])

    def test_failed_collector_overrides_threshold_exit(self):
        self.metadata.update(exit_code=99, collector_exit_code=1)
        self.write('metadata.json', self.metadata)
        self.assertEqual(self.detail()['status'], 'Data failure')

    def test_resource_gap_does_not_invalidate_collection(self):
        self.write('collection-check.json', {'valid': True, 'collection_errors': 1, 'warnings': ['Resource gap']})
        self.assertEqual(self.detail()['tone'], 'warn')

    def test_timeout_count_requires_complete_unique_events(self):
        events = [dict(event='completed', phase='load', request_id='a', error_category=None),
                  dict(event='completed', phase='load', request_id='b', error_category='timeout')]
        path = self.folder / 'request-events.jsonl'
        path.write_text('\n'.join(map(json.dumps, events)), encoding='utf-8')
        self.assertEqual(self.detail()['timeouts'], 1)
        path.write_text(json.dumps(events[0]), encoding='utf-8')
        self.assertIsNone(self.detail()['timeouts'])
        path.write_text('\n'.join([json.dumps(events[1])] * 2), encoding='utf-8')
        self.assertIsNone(self.detail()['timeouts'])

    def test_malformed_and_partial_files_remain_visible(self):
        (self.folder / 'summary.json').write_text('{', encoding='utf-8')
        self.assertEqual(self.detail()['status'], 'Read error')
        self.write('summary.json', {'metrics': []})
        self.assertEqual(self.detail()['status'], 'Read error')
        self.assertEqual(len(self.results.catalog()), 2)

    def test_series_completion_and_reviewed_interruption(self):
        series = next(row for row in self.results.catalog() if row['kind'] == 'series')
        self.assertEqual((series['completed'], series['total'], series['status']), (1, 18, 'Incomplete'))
        (self.folder.parent / 'review.json').write_text(json.dumps({'observed_status': 'interrupted_process_missing'}))
        series = self.results.detail('main/series')
        self.assertEqual(series['status'], 'Interrupted')
        self.assertEqual(len(series['children']), 1)

    def test_legacy_finished_run_is_not_marked_incomplete(self):
        self.write('metadata.json', {'load_finished_at_utc': '2026-10-16T12:00:00Z', 'load_exit_code': 0})
        (self.folder / 'assessment.json').unlink()
        (self.folder / 'collection-check.json').unlink()
        data = self.detail()
        self.assertTrue(data['complete'])
        self.assertEqual(data['status'], 'Not assessed')

    def test_reject_path_escape_and_results_root(self):
        for name in ('../outside', '.', str(self.root.parent)):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.results.path(name)

    def test_followup_uses_manifest_assessment_and_preserves_original(self):
        saved = Results(Path(__file__).resolve().parents[2] / 'results')
        series = 'follow-up/comparison-20261110-205108-peak12'
        third = saved.detail(series + '/attempt-03-fixed-3-burst')
        self.assertEqual((third['status'], third['p95_scope']), ('Target missed', 'Peak'))
        self.assertAlmostEqual(third['p95_ms'], 5116.45)
        overview = saved.detail(series)
        self.assertEqual((overview['completed'], overview['total'], overview['status']), (9, 9, 'Complete'))
        self.assertEqual((overview['target_met'], overview['target_assessed']), (2, 9))
        self.assertEqual(overview['preserved_originals'], 1)
        original = saved.detail(series + '/attempt-07-fixed-3-burst')
        self.assertEqual(original['status'], 'Data failure')
        self.assertTrue(original['name'].endswith('original'))
        recovered = saved.detail(series + '/attempt-07-fixed-3-burst-recovered')
        self.assertEqual(recovered['status'], 'Passed')
        self.assertAlmostEqual(recovered['p95_ms'], 4001.2)

    def test_real_saved_main_run_and_plot(self):
        saved = Results(Path(__file__).resolve().parents[2] / 'results')
        data = saved.detail('main/series-2026-10-25-v1.1/attempt-06-autoscaling-burst')
        self.assertAlmostEqual(data['p95_ms'], 3216.9)
        self.assertEqual((data['successful'], data['failed'], data['timeouts']), (336, 0, 0))
        self.assertTrue(saved.path(data['plot']).is_file())


if __name__ == '__main__':
    unittest.main()

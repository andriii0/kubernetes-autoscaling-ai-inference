import json
from pathlib import Path
import tempfile
import unittest

from lab.results import Results, policy_summary


class ResultTests(unittest.TestCase):
    def test_series_finds_direct_overview_without_changing_run_plot_lookup(self):
        series = self.folder.parent
        (series / 'primary-p95.png').write_bytes(b'overview')
        (self.folder / 'measurements.png').write_bytes(b'run')
        self.assertEqual(self.results.detail('main/series')['plot'], 'main/series/primary-p95.png')
        self.assertEqual(self.detail()['plot'], 'main/series/attempt-01-autoscaling-burst/measurements.png')

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

    def test_preparation_uses_peak_assessment_and_preserves_missing_values(self):
        for version in ('active-requests-preparation-v1', 'active-requests-preparation-v2'):
            for primary in ({'name': 'peak', 'p95_ms': 7000}, {'name': 'peak', 'p95_ms': None}, None):
                with self.subTest(version=version, primary=primary):
                    folder = self.root / 'custom-metric' / version / 'target-1'
                    folder.mkdir(parents=True, exist_ok=True)
                    metadata = {**self.metadata, 'extension_version': version, 'slo_ms': 5000}
                    metadata.pop('protocol_version')
                    (folder / 'metadata.json').write_text(json.dumps(metadata))
                    (folder / 'collection-check.json').write_text(json.dumps({'valid': True}))
                    (folder / 'summary.json').write_text(json.dumps({
                        'metrics': {'successful_latency_ms': {'p(95)': 1200}}}))
                    completed = [] if primary is None else [{'run': folder.name, 'assessment': {
                        'overall': 'fail', 'data_valid': True, 'primary': primary}}]
                    (folder.parent / 'manifest.json').write_text(json.dumps({
                        'protocol': version, 'completed': completed}))
                    run = self.results.detail(folder.relative_to(self.root).as_posix())
                    self.assertEqual((run['p95_scope'], run['p95_ms'], run['target_ms']),
                                     ('Peak', primary['p95_ms'] if primary else None, 5000))
                    if primary is not None:
                        self.assertEqual(run['status'], 'Target missed')

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
            completed.append({'run': name, 'policy': policy,
                              'assessment': {'overall': 'pass', 'data_valid': True,
                                             'primary': {'name': 'peak', 'failed': 1, 'p95_ms': 4000}},
                              'outcomes': {'peak_started': 10, 'peak_on_time_successes': 8}})
        failed = series / 'attempt-05-cpu'
        failed.mkdir()
        (failed / 'metadata.json').write_text(json.dumps({**self.metadata, 'exit_code': 1, 'collection_valid': False}))
        manifest = {'protocol': 'active-requests-comparison-v3', 'status': 'finished',
                    'cells': list(policies), 'completed': completed}
        (series / 'manifest.json').write_text(json.dumps(manifest))
        result = next(r for r in self.results.catalog() if r['id'] == 'custom-metric/comparison-resumed')
        self.assertEqual((result['status'], result['completed'], result['total']), ('Complete', 6, 6))
        self.assertEqual(result['preserved_originals'], 1)
        detail = self.results.detail('custom-metric/comparison-resumed')
        self.assertEqual(detail['policy'], 'comparison')
        for arm in detail['policies']:
            self.assertEqual((arm['runs'], arm['peak_started'], arm['peak_on_time_successes'],
                              arm['peak_errors'], arm['peak_p95_range_ms'], arm['target_met']),
                             (3, 30, 24, 3, [4000, 4000], 3))
        self.assertIn('custom-metric/comparison-resumed/attempt-05-cpu', result['attempts'])
        # A failed cell without an accepted replacement must still affect the status.
        manifest['completed'] = completed[:4]
        (series / 'manifest.json').write_text(json.dumps(manifest))
        (series / completed[4]['run'] / 'metadata.json').write_text(json.dumps({**self.metadata, 'exit_code': 1}))
        result = next(r for r in self.results.catalog() if r['id'] == 'custom-metric/comparison-resumed')
        self.assertEqual(result['status'], 'Needs review')
        self.assertEqual(result['preserved_originals'], 0)

    def test_pending_collection_is_unknown_until_checked_or_finalized(self):
        self.metadata.update(finished_at_utc=None, exit_code=None, collector_exit_code=None,
                             collection_valid=False, status='running')
        self.write('metadata.json', self.metadata)
        (self.folder / 'collection-check.json').unlink()
        (self.folder / 'assessment.json').unlink()
        pending = self.detail()
        self.assertEqual((pending['status'], pending['collection_valid']), ('Incomplete', None))
        self.assertFalse(pending['complete'])
        self.write('collection-check.json', {'valid': False})
        self.assertEqual((self.detail()['status'], self.detail()['collection_valid']), ('Data failure', False))
        (self.folder / 'collection-check.json').unlink()
        self.metadata.update(collector_exit_code=1)
        self.write('metadata.json', self.metadata)
        self.assertEqual(self.detail()['status'], 'Data failure')
        self.metadata.update(collector_exit_code=None, errors=['Launch failed'])
        self.write('metadata.json', self.metadata)
        self.assertEqual(self.detail()['status'], 'Run failed')
        self.metadata.update(errors=[], exit_code=1)
        self.write('metadata.json', self.metadata)
        self.assertEqual((self.detail()['status'], self.detail()['collection_valid']), ('Data failure', False))

    def test_policy_labels_survive_in_catalog_and_detail(self):
        for policy in ('cpu', 'active-1', 'active-2'):
            with self.subTest(policy=policy):
                self.metadata['custom_metric_policy'] = policy
                self.write('metadata.json', self.metadata)
                self.assertEqual(self.detail()['policy'], policy)
                self.assertEqual(self.results.run(self.folder)['policy'], policy)

    def test_policy_summary_keeps_missing_and_malformed_values_unknown(self):
        for bad in (None, '12', True, -1, float('nan'), float('inf')):
            with self.subTest(bad=bad):
                issues = []
                rows = [{'run': f'attempt-{i:02d}-cpu', 'policy': 'cpu',
                         'assessment': {'data_valid': True, 'overall': 'pass',
                                        'primary': {'name': 'peak', 'failed': bad if i == 2 else 0,
                                                    'p95_ms': bad if i == 2 else 4000}},
                         'outcomes': {'peak_started': 10, 'peak_on_time_successes': bad if i == 2 else 9}}
                        for i in (1, 2)]
                cpu, custom = policy_summary({'completed': rows}, issues)
                self.assertEqual(cpu['runs'], 2)
                for field in ('peak_on_time_fraction', 'peak_errors', 'peak_p95_range_ms'):
                    self.assertIsNone(cpu[field])
                self.assertEqual((custom['runs'], custom['target_assessed']), (0, 0))
                self.assertIsNone(custom['peak_errors'])
                self.assertIsNone(custom['peak_on_time_fraction'])
        rows[1]['outcomes']['peak_on_time_successes'] = 11
        self.assertIsNone(policy_summary({'completed': rows}, [])[0]['peak_on_time_fraction'])
        rows[1]['outcomes'] = []
        issues = []
        self.assertIsNone(policy_summary({'completed': rows}, issues)[0]['peak_on_time_fraction'])
        self.assertTrue(issues)

    def test_duplicate_accepted_run_is_not_counted_twice(self):
        row = {'run': 'attempt-01-cpu', 'policy': 'cpu', 'outcomes': {
            'peak_started': 10, 'peak_on_time_successes': 8}}
        issues = []
        cpu = policy_summary({'completed': [row, row]}, issues)[0]
        self.assertEqual((cpu['runs'], cpu['peak_started'], cpu['peak_on_time_fraction']), (1, 10, .8))
        self.assertTrue(issues)

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

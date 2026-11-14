import copy
from contextlib import nullcontext
import hashlib
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
            self.assertEqual(meta['extension_version'], 'active-requests-comparison-v3')
            self.assertEqual(meta['purpose'], 'custom-metric-comparison')
            self.assertNotIn('protocol_version', meta)
        with patch('sys.stderr', new=io.StringIO()), self.assertRaises(SystemExit):
            run_pilot.parse_arguments(prep.arguments(Path('unused'), 2, 'http://localhost:1') + ['--custom-metric-comparison'])

    def test_explicit_infrastructure_renewal_requires_original_and_same_images(self):
        original = {'gateway': {'uid': 'old', 'container_id': 'old-container', 'image_id': 'pinned'}}
        renewed = {'gateway': {'uid': 'new', 'container_id': 'new-container', 'image_id': 'pinned'}}
        record = {'previous_identity': original, 'identity': renewed, 'reason': 'Host reboot between pairs'}
        with patch.object(driver, 'read', return_value={'identity': original}):
            self.assertEqual(driver.recovered_identity(Path('prep'), record), renewed)
            for bad in ({**record, 'previous_identity': {}}, {**record, 'identity': {}},
                        {**record, 'reason': ''},
                        {**record, 'identity': {'gateway': {**renewed['gateway'], 'image_id': 'other'}}},
                        {**record, 'identity': {'gateway': {**renewed['gateway'], 'uid': ''}}}):
                with self.subTest(record=bad), self.assertRaises(ValueError):
                    driver.recovered_identity(Path('prep'), bad)

    def test_live_preflight_rejects_unrecorded_or_changed_recovered_instances(self):
        original = {'gateway': {'uid': 'old', 'container_id': 'old-container', 'image_id': 'pinned'}}
        renewed = {'gateway': {'uid': 'new', 'container_id': 'new-container', 'image_id': 'pinned'}}
        record = {'previous_identity': original, 'identity': renewed, 'reason': 'Host reboot between pairs'}
        from unittest.mock import Mock
        host = {'minikube_container': {'NanoCpus': 8000000000, 'Memory': 12884901888}}
        observer = Mock()
        observer.read.return_value = '{"items": []}'
        with patch.object(driver, 'host_snapshot', return_value=host), \
             patch.object(driver, 'configuration', return_value={}), \
             patch.object(driver, 'read', return_value={'identity': original}), \
             patch.object(driver, 'infrastructure_identity', return_value=renewed):
            with self.assertRaisesRegex(ValueError, 'metrics infrastructure changed'):
                driver.live_preflight(observer, Path('prep'), Path('bundle'), None)
            observer.collect.side_effect = ValueError('reached backend validation')
            with self.assertRaisesRegex(ValueError, 'reached backend validation'):
                driver.live_preflight(observer, Path('prep'), Path('bundle'), None, record)
            changed = {'gateway': {**renewed['gateway'], 'uid': 'unrecorded'}}
            with patch.object(driver, 'infrastructure_identity', return_value=changed):
                with self.assertRaisesRegex(ValueError, 'metrics infrastructure changed'):
                    driver.live_preflight(observer, Path('prep'), Path('bundle'), None, record)

    def test_same_recovery_record_is_reusable_after_fifth_accepted_cell(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            saved = folder / 'resume-old'
            saved.mkdir()
            recovery = {'identity': {'gateway': {'uid': 'same'}}, 'reason': 'previous recovery'}
            (saved / 'infrastructure-recovery.json').write_text(json.dumps(recovery))
            manifest = {'completed': driver.CELLS[:5], 'preparation_dir': str(folder),
                        'continuations': [{'record': 'resume-old'}]}
            state = (manifest, {}, driver.CELLS[5:], {})
            args = ['--output-dir', str(folder), '--preparation-dir', str(folder), '--resume']
            with patch.object(driver, 'preparation_evidence', return_value={}), \
                 patch.object(driver, 'resume_state', return_value=state), \
                 patch.object(driver, 'recovered_identity') as validate, patch('sys.stdout', new=io.StringIO()):
                self.assertEqual(driver.main(args), 0)
                validate.assert_called_with(folder, recovery)
                self.assertEqual(driver.main(args + ['--recovered-infrastructure-record', str(saved / 'infrastructure-recovery.json')]), 0)
                other = folder / 'other.json'
                other.write_text(json.dumps({**recovery, 'reason': 'new renewal'}))
                with self.assertRaisesRegex(ValueError, 'between complete pairs'):
                    driver.main(args + ['--recovered-infrastructure-record', str(other)])

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

    def test_failed_preparation_reports_original_error_before_loading_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            meta = {'exit_code': 1, 'errors': ['Prometheus and observer clocks differ by more than one second']}
            path = folder / 'metadata.json'
            path.write_text(json.dumps(meta))
            before = path.read_bytes()
            with patch.object(prep, 'load_results') as load:
                with self.assertRaisesRegex(ValueError, 'clocks differ') as error:
                    prep.review(folder, 1, comparison=True)
                load.assert_not_called()
            self.assertIn('missing request evidence: request-events.jsonl, summary.json', str(error.exception))
            self.assertEqual(path.read_bytes(), before)

    def test_failed_launcher_without_recorded_errors_keeps_exit_code(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'metadata.json').write_text(json.dumps({'exit_code': 1, 'errors': []}))
            with self.assertRaisesRegex(ValueError, 'launcher exited with code 1'):
                prep.review(folder, 1)

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


class ResumeComparisonTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / 'series'
        self.folder.mkdir()
        (self.folder / 'inputs').mkdir()
        (self.root / 'bench').mkdir()
        self.sources = {}
        for name in ('run_custom_comparison.py', 'prepare_custom_metric.py', 'observe.py'):
            (self.folder / 'inputs' / name).write_bytes(b'original')
            (self.root / 'bench' / name).write_bytes(b'original')
            self.sources[name] = hashlib.sha256(b'original').hexdigest()
        self.current = dict(self.sources)
        self.save('source-sha256.json', self.sources)
        self.result = {'qualification': None, 'assessment': {'overall': 'fail', 'primary': {'p95_ms': 7000}},
                       'phases': [], 'custom_metric_check': {'valid': True},
                       'outcomes': {'peak_on_time_fraction': .5, 'peak_error_fraction': 0}, 'resources': {}}
        self.meta = {'source_sha256': self.sources, 'exit_code': 99, 'custom_metric_policy': 'cpu',
                     'duration_seconds': 782, 'rate': 12, 'low_rate': 2, 'post_seconds': 300,
                     'mode': 'autoscaling', 'profile': 'burst', 'initial_identity': {'image_id': 'image'}}
        completed = []
        for cell in driver.CELLS[:4]:
            run = f"attempt-{cell['order']:02d}-{cell['policy']}"
            output = f"attempt-{cell['order']:02d}-analysis"
            self.save(run + '/metadata.json', {**self.meta, 'custom_metric_policy': cell['policy']})
            self.save(output + '/comparison.json', self.result)
            completed.append({**cell, 'run': run, 'analysis': output, **copy.deepcopy(self.result)})
        self.failed = self.save('attempt-05-cpu/metadata.json', {'exit_code': 1, 'collection_valid': False})
        self.save('preflight.json', {'host': {}})
        (self.root / 'target-2').mkdir()
        (self.root / 'target-2/metadata.json').write_text(json.dumps(self.meta))
        self.manifest = {'status': 'stopped', 'protocol': 'active-requests-comparison-v2', 'selected_target': 1,
                         'cells': driver.CELLS, 'completed': completed, 'current': 'attempt-05-cpu',
                         'preparation_dir': str(self.root), 'errors': ['local kubectl crash']}
        self.save('manifest.json', self.manifest)
        for target, options in (
            ('ROOT', {'new': self.root}),
            ('source_hashes', {'side_effect': lambda: self.current}),
            ('review', {'side_effect': self.review}),
            ('load_results', {'return_value': {}}),
            ('outcomes', {'return_value': self.result['outcomes']}),
            ('primary_resources', {'return_value': {}}),
        ):
            patcher = patch.object(driver, target, **options)
            patcher.start()
            self.addCleanup(patcher.stop)

    def save(self, relative, value):
        path = self.folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def review(self, *args, **kwargs):
        return {k: copy.deepcopy(v) for k, v in self.result.items() if k not in ('outcomes', 'resources')}

    def hashes(self):
        return {p.relative_to(self.folder).as_posix(): p.read_bytes()
                for p in self.folder.rglob('*') if p.is_file()}

    def test_prefix_replay_is_read_only_and_accepts_target_misses(self):
        before = self.hashes()
        manifest, current, pending, changes = driver.resume_state(self.folder)
        self.assertEqual([c['order'] for c in pending], [5, 6])
        self.assertEqual(len(manifest['completed']), 4)
        self.assertEqual(changes, {})
        self.assertEqual(self.hashes(), before)
        self.assertTrue(all(c.kwargs['source_dir'] == self.folder / 'inputs'
                            for c in driver.review.call_args_list))

    def test_changed_collector_and_corrupt_archive_are_rejected(self):
        self.current['observe.py'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'collector changed'):
            driver.resume_state(self.folder)
        self.current['observe.py'] = self.sources['observe.py']
        (self.folder / 'inputs/observe.py').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'archive changed'):
            driver.resume_state(self.folder)

    def test_only_driver_and_archived_review_changes_are_admitted(self):
        for name in ('run_custom_comparison.py', 'prepare_custom_metric.py'):
            (self.root / 'bench' / name).write_bytes(b'continuation')
            self.current[name] = hashlib.sha256(b'continuation').hexdigest()
        _, _, _, changes = driver.resume_state(self.folder)
        self.assertEqual(set(changes), {'run_custom_comparison.py', 'prepare_custom_metric.py'})
        with patch.object(driver, 'preparation_evidence', return_value={}), \
             patch.object(driver, 'run_command') as launch, patch('sys.stdout', new=io.StringIO()) as output:
            before = self.hashes()
            self.assertEqual(driver.main(['--output-dir', str(self.folder), '--preparation-dir', str(self.root),
                                          '--resume']), 0)
            self.assertEqual(self.hashes(), before)
            self.assertEqual(json.loads(output.getvalue())['accepted'], 4)
        launch.assert_not_called()

    def test_changed_settings_prefix_or_result_are_rejected(self):
        original = copy.deepcopy(self.manifest)
        self.manifest['completed'][1]['order'] = 3
        self.save('manifest.json', self.manifest)
        with self.assertRaisesRegex(ValueError, 'consecutive prefix'):
            driver.resume_state(self.folder)
        self.manifest = copy.deepcopy(original)
        self.manifest['completed'][0]['assessment']['overall'] = 'pass'
        self.save('manifest.json', self.manifest)
        with self.assertRaisesRegex(ValueError, 'result differs'):
            driver.resume_state(self.folder)
        self.save('manifest.json', original)
        self.save('attempt-01-cpu/metadata.json', {**self.meta, 'rate': 8})
        with self.assertRaisesRegex(ValueError, 'settings'):
            driver.resume_state(self.folder)

    def test_assessable_stopped_attempt_is_not_repeated(self):
        self.save('attempt-05-cpu/metadata.json', {'exit_code': 99, 'collection_valid': True})
        with self.assertRaisesRegex(ValueError, 'not replacement load'):
            driver.resume_state(self.folder)

    def test_retry_path_preserves_original_and_rejects_analysis_collision(self):
        before = self.failed.read_bytes()
        run, output = driver.next_paths(self.folder, driver.CELLS[4])
        self.assertEqual(run.name, 'attempt-05-cpu-retry-01')
        self.assertEqual(self.failed.read_bytes(), before)
        output.mkdir()
        with self.assertRaisesRegex(ValueError, 'destination already exists'):
            driver.next_paths(self.folder, driver.CELLS[4])

    def execute(self, fail=False, fail_next_preflight=False):
        def launch(command, run):
            run.mkdir(exist_ok=False)
            policy = command[command.index('--custom-metric-policy') + 1]
            (run / 'metadata.json').write_text(json.dumps(
                {**self.meta, 'custom_metric_policy': policy, 'source_sha256': self.current}))
            return 1 if fail else 99
        def analyze(args):
            Path(args[args.index('--output-dir') + 1]).mkdir()
            return 0
        original_review = self.review
        def review(run, *args, **kwargs):
            if fail and 'retry' in run.name:
                raise ValueError('new cleanup failed')
            return original_review(run, *args, **kwargs)
        with patch.object(driver, 'preparation_evidence', return_value={}), \
             patch.object(driver, 'live_preflight', side_effect=[{'host': {}}, {'host': {}}, ValueError('next preflight failed')] if fail_next_preflight else None, return_value={'host': {}}), \
             patch.object(driver, 'gateway_url', return_value=nullcontext('http://localhost:1')), \
             patch.object(driver, 'run_command', side_effect=launch) as launched, \
             patch.object(driver, 'analyze', side_effect=analyze), \
             patch.object(driver, 'review', side_effect=review):
            code = driver.main(['--output-dir', str(self.folder), '--preparation-dir', str(self.root),
                                '--resume', '--execute'])
        return code, launched

    def test_resume_launches_only_two_remaining_cells_and_preserves_failed_attempt(self):
        before = self.hashes()
        code, launched = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual([c.args[1].name for c in launched.call_args_list],
                         ['attempt-05-cpu-retry-01', 'attempt-06-active-1'])
        manifest = json.loads((self.folder / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'finished')
        self.assertEqual(manifest['completed'][:4], self.manifest['completed'])
        self.assertEqual(len(manifest['completed']), 6)
        self.assertFalse((self.folder / 'resume.lock').exists())
        for name, payload in before.items():
            if name != 'manifest.json':
                self.assertEqual((self.folder / name).read_bytes(), payload)

    def test_failed_replacement_stops_before_sixth_cell_and_releases_lock(self):
        code, launched = self.execute(fail=True)
        self.assertEqual(code, 1)
        launched.assert_called_once()
        manifest = json.loads((self.folder / 'manifest.json').read_text())
        self.assertEqual(len(manifest['completed']), 4)
        self.assertEqual(manifest['status'], 'stopped')
        self.assertFalse((self.folder / 'resume.lock').exists())

    def test_preflight_failure_after_acceptance_keeps_only_sixth_cell_pending(self):
        code, launched = self.execute(fail_next_preflight=True)
        self.assertEqual(code, 1)
        launched.assert_called_once()
        before = self.hashes()
        manifest, _, pending, _ = driver.resume_state(self.folder)
        self.assertEqual(len(manifest['completed']), 5)
        self.assertEqual([cell['order'] for cell in pending], [6])
        self.assertEqual(self.hashes(), before)

    def test_existing_resume_lock_stops_before_any_launch(self):
        (self.folder / 'resume.lock').write_text('another driver')
        with patch.object(driver, 'preparation_evidence', return_value={}), \
             patch.object(driver, 'run_command') as launch, self.assertRaises(FileExistsError):
            driver.main(['--output-dir', str(self.folder), '--preparation-dir', str(self.root),
                         '--resume', '--execute'])
        launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()

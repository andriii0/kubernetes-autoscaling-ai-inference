import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import run_series as series


class SeriesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.row = series.matrix()[0]
        self.result = dict(data_valid=True, duration_complete=True, unfinished=0, dropped=0, overall='pass')

    def saved_data(self):
        metadata = dict(self.row, actual_order=1, protocol_version='1.1', exit_code=0,
                        collector_exit_code=0, errors=[], collection_valid=True, warnings=[])
        return dict(metadata=metadata, check=dict(warnings=[]))

    def review(self, data, result):
        with patch.object(series, 'load_results', return_value=data), \
                patch.object(series, 'check_inputs'), \
                patch.object(series, 'assessment', return_value=result), \
                patch.object(series, 'read_json', return_value=result):
            return series.review(self.root, self.row)

    def test_target_failure_is_retained(self):
        data = self.saved_data()
        data['metadata']['exit_code'] = 99
        result = dict(self.result, overall='fail')
        self.assertEqual(self.review(data, result), result)

    def test_incomplete_or_invalid_result_stops(self):
        for change in (dict(data_valid=False), dict(duration_complete=False), dict(unfinished=1),
                       dict(dropped=1), dict(overall='not_assessable')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.review(self.saved_data(), dict(self.result, **change))

    def test_unreviewed_warning_stops_but_existing_boundary_rule_is_retained(self):
        data = self.saved_data()
        data['check']['warnings'] = [series.BOUNDARY_WARNING]
        self.review(data, self.result)
        data['check']['warnings'].append('missing archive hash')
        with self.assertRaisesRegex(ValueError, 'warnings require review'):
            self.review(data, self.result)

    def test_wrong_matrix_identity_and_collector_failure_stop(self):
        for change in (dict(actual_order=2), dict(mode='fixed-3'), dict(collector_exit_code=1),
                       dict(exit_code=130), dict(collection_valid=False), dict(errors=['failed'])):
            data = self.saved_data()
            data['metadata'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.review(data, self.result)

    def test_changed_executable_is_rejected(self):
        (self.root / 'bench').mkdir()
        (self.root / 'bench/workload.json').write_text('{}')
        with patch.object(series, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'input changed'):
            series.check_inputs(dict(source_sha256={'workload.json': '0' * 64}))

    def test_resume_skips_completed_prefix_and_rejects_partial_attempt(self):
        folder, output = series.paths(self.root, self.row)
        folder.mkdir()
        (self.root / 'attempt-01-console.txt').write_text('saved console')
        with patch.object(series, 'review', return_value=self.result) as review, \
                patch.object(series, 'check_analysis'):
            pending = series.pending_rows(self.root)
        self.assertEqual([row['planned_order'] for row in pending], list(range(2, 19)))
        review.assert_called_once_with(folder, self.row)
        with patch.object(series, 'review', side_effect=ValueError('partial attempt')):
            with self.assertRaisesRegex(ValueError, 'partial attempt'):
                series.pending_rows(self.root)

    def test_replacement_or_gap_requires_manual_review(self):
        (self.root / 'attempt-19-fixed-1-steady').mkdir()
        with self.assertRaisesRegex(ValueError, 'Unexpected attempt'):
            series.pending_rows(self.root)
        (self.root / 'attempt-19-fixed-1-steady').rmdir()
        series.paths(self.root, series.matrix()[1])[0].mkdir()
        with self.assertRaisesRegex(ValueError, 'consecutive prefix'):
            series.pending_rows(self.root)

    def test_existing_partial_analysis_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete analysis'):
            series.check_analysis(self.root, self.root / 'analysis', self.result)

    def test_collection_failure_does_not_launch_analyzer_or_next_run(self):
        with patch.object(series, 'run_command', return_value=1) as run:
            with self.assertRaisesRegex(ValueError, 'launcher exit 1'):
                series.execute(self.root, series.matrix()[:2], 'http://localhost:1234', 'none')
        self.assertEqual(run.call_count, 1)

    def test_exit_99_continues_after_review_and_analysis(self):
        with patch.object(series, 'run_command', side_effect=[99, 0, 0, 0]) as run, \
                patch.object(series, 'review', return_value=dict(self.result, overall='fail')), \
                patch.object(series, 'check_analysis'):
            series.execute(self.root, series.matrix()[:2], 'http://localhost:1234', 'none')
        self.assertEqual(run.call_count, 4)
        first = run.call_args_list[0].args[0]
        self.assertEqual(first[first.index('--planned-order') + 1], '1')
        self.assertIn('--no-plots', run.call_args_list[1].args[0])

    def test_dry_run_has_no_runtime_calls_or_new_files(self):
        with patch.object(series, 'pending_rows', return_value=series.matrix()[10:]), \
                patch.object(series, 'service_url') as tunnel, \
                patch.object(series, 'run_command') as run, redirect_stdout(io.StringIO()):
            self.assertEqual(series.main(['--series-dir', str(self.root), '--dry-run']), 0)
        tunnel.assert_not_called()
        run.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_external_tunnel_is_reused_without_starting_minikube(self):
        with patch.object(series, 'run_command') as run, series.service_url('http://localhost:1234') as url:
            self.assertEqual(url, 'http://localhost:1234')
        run.assert_not_called()

    def test_owned_tunnel_is_closed_after_failure(self):
        tunnel = Mock()
        tunnel.poll.return_value = None

        def open_tunnel(*args, **kwargs):
            kwargs['stdout'].write('http://127.0.0.1:54321\n')
            kwargs['stdout'].flush()
            return tunnel

        with patch.object(series, 'run_command', return_value=0), \
                patch.object(series.subprocess, 'Popen', side_effect=open_tunnel):
            with self.assertRaisesRegex(ValueError, 'stop'):
                with series.service_url(None) as url:
                    self.assertEqual(url, 'http://127.0.0.1:54321')
                    raise ValueError('stop')
        tunnel.terminate.assert_called_once()
        tunnel.wait.assert_called_once_with(timeout=10)


if __name__ == '__main__':
    unittest.main()

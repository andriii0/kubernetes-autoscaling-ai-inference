import sys
import json
import shutil
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bench'))
import resume_peak12


class ResumeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.series = Path(temporary.name)
        self.cells = [
            dict(order=1, mode='fixed-1', repetition=1),
            dict(order=2, mode='autoscaling', repetition=1),
            dict(order=3, mode='fixed-3', repetition=1),
        ]
        self.driver = Mock(VERSION='test', CELLS=self.cells)
        self.driver.read.side_effect = lambda path: json.loads(path.read_text())
        self.driver.review.return_value = ({'overall': 'fail'}, [], {})
        self.manifest = dict(protocol='test', cells=self.cells)
        self.write('manifest.json', self.manifest)

    def write(self, relative, value):
        path = self.series / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def attempt(self, order, code=0, suffix=''):
        cell = self.cells[order - 1]
        name = f"attempt-{order:02d}-{cell['mode']}-burst{suffix}"
        self.write(f'{name}/metadata.json', {'exit_code': code})
        return name

    def test_replay_accepts_target_miss_and_leaves_only_suffix_pending(self):
        self.attempt(1, 99)
        original = (self.series / 'manifest.json').read_bytes()
        _, _, saved, pending = resume_peak12.replay(self.driver, self.series)
        self.assertEqual([cell['order'] for cell, _, _ in saved], [1])
        self.assertEqual([cell['order'] for cell in pending], [2, 3])
        self.assertEqual(self.driver.review.call_args.args[2], 99)
        self.driver.save.assert_not_called()
        self.assertEqual((self.series / 'manifest.json').read_bytes(), original)

    def test_replay_rejects_protocol_order_gap_and_partial_attempts(self):
        for change in ({'protocol': 'other'}, {'cells': self.cells[::-1]}):
            with self.subTest(change=change):
                self.write('manifest.json', {**self.manifest, **change})
                with self.assertRaisesRegex(ValueError, 'protocol or order'):
                    resume_peak12.replay(self.driver, self.series)
        self.write('manifest.json', self.manifest)
        self.attempt(2)
        with self.assertRaisesRegex(ValueError, 'consecutive prefix'):
            resume_peak12.replay(self.driver, self.series)
        for code in (None, 1, 130):
            with self.subTest(code=code):
                self.attempt(1, code)
                with self.assertRaisesRegex(ValueError, 'Partial or failed'):
                    resume_peak12.replay(self.driver, self.series)
        self.driver.review.assert_not_called()
        self.driver.save.assert_not_called()

    def test_replay_uses_separate_recovery_and_preserves_failed_original(self):
        original = self.attempt(1, 1)
        recovered = self.attempt(1, 0, '-recovered')
        self.write('log-recovery.json', {'runs': {original: recovered}})
        _, _, saved, _ = resume_peak12.replay(self.driver, self.series)
        self.assertEqual(saved[0][1], self.series / recovered)
        self.assertEqual(self.driver.review.call_args.args[0], self.series / recovered)
        self.assertEqual(json.loads((self.series / original / 'metadata.json').read_text())['exit_code'], 1)
        self.driver.save.assert_not_called()

    def test_record_rejects_changed_assessment_without_replacing_it(self):
        path = self.write('attempt-01-analysis/comparison-assessment.json', {'overall': 'pass'})
        manifest = {'completed_runs': []}
        with self.assertRaisesRegex(ValueError, 'Existing assessment differs'):
            resume_peak12.record(self.driver, self.series, self.cells[0],
                                 self.series / 'attempt-01-fixed-1-burst',
                                 ({'overall': 'fail'}, [], {}), manifest)
        self.assertEqual(json.loads(path.read_text()), {'overall': 'pass'})
        self.assertEqual(manifest['completed_runs'], [])
        self.driver.save.assert_not_called()
        self.driver.analyze.assert_not_called()

    def test_saved_prefix_replays_without_writes(self):
        series = Path('results/follow-up/comparison-20261110-205108-peak12').resolve()
        driver = resume_peak12.load_driver(series)
        # Historical replay uses historical executable inputs. The production
        # resume path must still reject a changed working tree before new load.
        reference = self.series / 'archived-source'
        for folder in sorted(series.glob('attempt-*/inputs')):
            metadata = json.loads((folder.parent / 'metadata.json').read_text())
            for name in metadata['source_sha256']:
                destination = reference / ('deploy' if name.endswith('.yaml') else 'bench') / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(folder / name, destination)
        with patch.object(driver, 'save', side_effect=AssertionError('Replay wrote evidence')), \
                patch.dict(resume_peak12.review.__globals__, ROOT=reference):
            _, _, saved, pending = resume_peak12.replay(driver, series)
        orders = [cell['order'] for cell, _, _ in saved]
        self.assertEqual(orders, list(range(1, len(saved) + 1)))
        self.assertEqual([cell['order'] for cell in pending], list(range(len(saved) + 1, 10)))
        self.assertGreaterEqual(len(saved), 7)
        result = saved[2][2][0]
        self.assertTrue(result['data_valid'])
        self.assertEqual(result['overall'], 'fail')
        self.assertAlmostEqual(result['primary']['p95_ms'], 5116.45)

    def test_missing_replica_does_not_reach_assessor(self):
        data = {'metadata': {'mode': 'fixed-3', 'initial_identity': [
            {'pod_uid': name} for name in ('a', 'b', 'c')]},
            'check': {'distribution': {'pods': {'a': {'completed': 10}, 'b': {'completed': 10}}}}}
        assess = Mock()
        with self.assertRaisesRegex(ValueError, 'three initial pods'):
            resume_peak12.comparison_assessment(data, assess)
        assess.assert_not_called()

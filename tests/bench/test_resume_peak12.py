import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bench'))
import resume_peak12


class ResumeTests(unittest.TestCase):
    def test_saved_prefix_replays_without_writes(self):
        series = Path('results/follow-up/comparison-20261110-205108-peak12').resolve()
        driver = resume_peak12.load_driver(series)
        with patch.object(driver, 'save', side_effect=AssertionError('Replay wrote evidence')):
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

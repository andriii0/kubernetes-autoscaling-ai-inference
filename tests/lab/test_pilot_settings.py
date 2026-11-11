import io
from pathlib import Path
import unittest
from unittest.mock import patch

from lab.launch import main, pilot_settings


class PilotSettingsTests(unittest.TestCase):
    def test_invalid_settings(self):
        for value in ([], {'unknown': 1}, {'rate': True}, {'rate': 0},
                      {'slo_ms': float('nan')}, {'duration_seconds': 0},
                      {'mode': 'autoscaling'}, {'profile': 'burst', 'duration_seconds': 60},
                      {'profile': 'burst', 'rate': 1, 'low_rate': 2}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                pilot_settings(value)

    def test_custom_dry_commands_create_no_results(self):
        root = Path(__file__).resolve().parents[2] / 'results/pilot'
        before = set(root.glob('ui-*'))
        for args, expected in (
            (['--mode', 'fixed-3', '--rate', '7', '--duration', '45s', '--slo-ms', '2500'],
             ['--mode fixed-3', '--rate 7', '--duration 45s', '--slo-ms 2500']),
            (['--mode', 'autoscaling', '--profile', 'burst', '--rate', '12', '--low-rate', '3'],
             ['--mode autoscaling', '--profile burst', '--rate 12', '--low-rate 3'])):
            with patch('sys.stdout', new_callable=io.StringIO) as output:
                self.assertEqual(main(['--dry-run', '--activity-note', 'test', *args]), 0)
            for text in expected:
                self.assertIn(text, output.getvalue())
            if 'burst' in args:
                self.assertNotIn('--duration', output.getvalue())
        self.assertEqual(set(root.glob('ui-*')), before)

import tempfile
import unittest
from contextlib import nullcontext
import json
from pathlib import Path
from unittest.mock import patch

import run_pilot_search


class PilotSearchTests(unittest.TestCase):
    def test_target_boundary_and_error_denominator(self):
        self.assertFalse(run_pilot_search.target_missed(5000, 2, 240))
        self.assertTrue(run_pilot_search.target_missed(5000.1, 0, 240))
        self.assertTrue(run_pilot_search.target_missed(1200, 3, 240))
        with self.assertRaises(ValueError):
            run_pilot_search.target_missed(None, 240, 240)

    def test_confirmation_requires_both_repetitions_and_fixed_order(self):
        rows = [dict(label=label, target_missed=label.startswith('peak'))
                for label in ('low-1', 'peak-1', 'low-2', 'peak-2')]
        self.assertTrue(run_pilot_search.confirmation_passes(rows))
        rows[-1]['target_missed'] = False
        self.assertFalse(run_pilot_search.confirmation_passes(rows))
        self.assertFalse(run_pilot_search.confirmation_passes(rows[:2]))

    def test_existing_series_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(run_pilot_search, 'service_url') as tunnel:
            with self.assertRaises(FileExistsError):
                run_pilot_search.main(['--series-dir', temporary])
            tunnel.assert_not_called()

    def test_search_stops_at_first_peak_and_runs_only_four_confirmations(self):
        def inspected(folder, seconds):
            rate = int(folder.name.rsplit('-', 1)[1])
            return (dict(rate=rate, target_missed=rate >= 10, response_failure=False,
                         p95_ms=6000 if rate >= 10 else 1200, failed=0), {})
        with tempfile.TemporaryDirectory() as temporary:
            series = Path(temporary) / 'new-series'
            with patch.object(run_pilot_search, 'service_url', return_value=nullcontext('http://127.0.0.1:1')), \
                    patch.object(run_pilot_search, 'host_snapshot', return_value={'minikube_container': {}, 'power_scheme_guid': 'test'}), \
                    patch.object(run_pilot_search, 'run_command', return_value=0) as launch, \
                    patch.object(run_pilot_search, 'inspect', side_effect=inspected), \
                    patch.object(run_pilot_search.analyze, 'main', return_value=0):
                self.assertEqual(run_pilot_search.main(['--series-dir', str(series)]), 0)
            rates = [int(call.args[0][call.args[0].index('--rate') + 1]) for call in launch.call_args_list]
            self.assertEqual(rates, [2, 8, 10, 2, 10, 2, 10])
            manifest = json.loads((series / 'manifest.json').read_text())
            self.assertTrue(manifest['selection_confirmed'])
            self.assertEqual(manifest['status'], 'finished')

    def test_collection_failure_prevents_next_probe(self):
        with tempfile.TemporaryDirectory() as temporary:
            series = Path(temporary) / 'new-series'
            with patch.object(run_pilot_search, 'service_url', return_value=nullcontext('http://127.0.0.1:1')), \
                    patch.object(run_pilot_search, 'host_snapshot', return_value={}), \
                    patch.object(run_pilot_search, 'run_command', return_value=0) as launch, \
                    patch.object(run_pilot_search, 'inspect', side_effect=ValueError('incomplete delivery')):
                self.assertEqual(run_pilot_search.main(['--series-dir', str(series)]), 1)
            self.assertEqual(launch.call_count, 1)
            self.assertEqual(json.loads((series / 'manifest.json').read_text())['status'], 'stopped')


if __name__ == '__main__':
    unittest.main()

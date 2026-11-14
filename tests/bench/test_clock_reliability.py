import hashlib
import json
import math
from pathlib import Path
import subprocess
import unittest

from custom_metrics import validate_clock, validate_observer_interval
from tests.bench.fixtures import RunFixture


class ClockTests(unittest.TestCase):
    def test_scheduling_pause_within_a_clock_read_is_not_a_proven_step(self):
        from unittest.mock import patch
        from custom_metrics import clock_point
        with patch("custom_metrics.time.monotonic", side_effect=[10, 10.2]), patch("custom_metrics.time.time", return_value=100):
            wall, mono, uncertainty = clock_point()
        self.assertAlmostEqual(uncertainty, .1)
        validate_observer_interval(wall, 100.2, mono, 10.2, uncertainty, 0)
        with self.assertRaisesRegex(ValueError, "observer wall clock changed"):
            validate_observer_interval(wall, 101.2, mono, 10.2, uncertainty, 0)

    def test_wall_step_is_distinct_from_server_skew(self):
        validate_observer_interval(100, 100.2, 20, 20.2)
        with self.assertRaisesRegex(ValueError, 'observer wall clock changed'):
            validate_observer_interval(100, 101.2, 20, 20.2)
        with self.assertRaisesRegex(ValueError, 'observer wall clock changed'):
            validate_observer_interval(100, 99.2, 20, 20.2)
        with self.assertRaisesRegex(ValueError, 'Prometheus and observer'):
            validate_clock(101.6, 100, 100.2)

    def test_replay_checks_adapter_and_between_query_clock_steps(self):
        from custom_metric_run import validate_record_clock
        bracket = {}
        for side in ("before", "adapter", "after"):
            for edge in ("sent", "received"):
                value = 100 + len(bracket) / 100
                bracket[f"{side}_{edge}_at"] = value
                bracket[f"{side}_{edge}_monotonic"] = value - 80
        record = dict(started_at=100, started_monotonic=20, brackets=[bracket])
        validate_record_clock(record)
        with self.assertRaisesRegex(ValueError, "observer wall clock changed"):
            validate_record_clock(record, (99, 19.2))
        bracket["adapter_received_at"] += .2
        with self.assertRaisesRegex(ValueError, "observer wall clock changed"):
            validate_record_clock(record)

    def test_nonfinite_and_reversed_monotonic_intervals_are_rejected(self):
        for values in ((100, 101, 20, 19), (100, math.nan, 20, 21)):
            with self.assertRaises(ValueError):
                validate_observer_interval(*values)

    def test_real_k6_timer_is_independent_of_javascript_wall_clock(self):
        from build_k6 import runtime
        binary, _ = runtime()
        script = """import clock from 'k6/x/monotonic'; import {sleep} from 'k6';
export const options={vus:1,iterations:1};
export default function(){const wall=Date.now(), before=clock.now();
Date.now=()=>wall+5000; sleep(.02);
console.log(JSON.stringify({elapsed:clock.now()-before,wall:Date.now()-wall}));}"""
        result = subprocess.run([str(binary), 'run', '--quiet', '--log-format', 'raw', '--log-output', 'stdout', '-'],
                                input=script, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        row = next(json.loads(line) for line in result.stdout.splitlines() if line.startswith('{'))
        self.assertEqual(row['wall'], 5000)
        self.assertGreaterEqual(row['elapsed'], 15)
        self.assertLess(row['elapsed'], 2000)


class MonotonicRecordsTests(RunFixture):
    def setUp(self):
        super().setUp()
        folder = self.folder / 'inputs/monotonic'
        folder.mkdir()
        sources = {}
        for name in ('monotonic.go', 'go.mod', 'go.sum'):
            data = name.encode()
            (folder / name).write_bytes(data)
            sources[name] = hashlib.sha256(data).hexdigest()
        self.metadata.update(latency_clock='monotonic-v1', timing_runtime={
            'sources': sources, 'binary_sha256': 'a' * 64})
        for event in self.events:
            event.update(schema_version=2, latency_clock='monotonic-v1', started_monotonic_ms=1000)
        self.completed['finished_monotonic_ms'] = 1500

    def test_monotonic_events_reconcile_and_old_fixture_remains_supported(self):
        self.assertTrue(self.check()['valid'])
        legacy = RunFixture()
        legacy.setUp()
        try:
            self.assertTrue(legacy.check()['valid'])
        finally:
            legacy.doCleanups()

    def test_wall_clock_jump_cannot_silently_change_accepted_latency(self):
        self.completed['finished_at_utc'] = '2026-10-18T12:00:03.500Z'
        result = self.check()
        self.assertFalse(result['valid'])
        self.assertTrue(any('wall clock changed' in e for e in result['errors']))
        self.assertEqual(self.completed['duration_ms'], 500)

    def test_rewritten_wall_and_duration_do_not_override_monotonic_interval(self):
        self.completed.update(finished_at_utc='2026-10-18T12:00:01.001Z', duration_ms=1)
        result = self.check()
        self.assertFalse(result['valid'])
        self.assertTrue(any('inconsistent request duration' in e for e in result['errors']))

    def test_missing_clock_fields_and_modified_timer_archive_fail(self):
        del self.completed['finished_monotonic_ms']
        self.assertFalse(self.check()['valid'])
        self.completed['finished_monotonic_ms'] = 1500
        (self.folder/'inputs/monotonic/monotonic.go').write_text('changed')
        result = self.check()
        self.assertTrue(any('timer archive changed' in e for e in result['errors']))

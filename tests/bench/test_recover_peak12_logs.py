import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bench'))
import recover_peak12_logs as recovery


class LogRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.series = Path(temporary.name)
        self.source = self.series / 'attempt-07-fixed-3-burst'
        (self.source / 'pod-logs').mkdir(parents=True)
        (self.source / 'pod-logs/uid.log').write_text('2026-11-10T12:00:02Z saved\n')
        self.meta = dict(k6_exit_code=99, collector_exit_code=0, errors=[],
                         source_sha256={'run_pilot.py': 'old-source'}, exit_code=1, collection_valid=False)
        (self.source / 'metadata.json').write_text(json.dumps(self.meta))
        (self.source / 'request-events.jsonl').write_bytes(b'preserved client events\n')
        self.target = self.source.with_name(self.source.name + '-recovered')
        self.raw = b'2026-11-10T12:00:01Z stdout F recovered\n'
        self.report = dict(valid=True, counts={'completed': 457}, warnings=[])
        self.argv = ['recover', '--series-dir', str(self.series), '--attempt', self.source.name,
                     '--uid', 'uid', '--node-log', '/saved/log']
        self.before = {p.relative_to(self.source): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}

    def invoke(self, raw=None, report=None):
        with patch.object(sys, 'argv', self.argv), \
                patch.object(recovery.subprocess, 'run', return_value=Mock(stdout=self.raw if raw is None else raw)), \
                patch.object(recovery, 'reconcile', return_value=self.report if report is None else report):
            recovery.main()

    def tearDown(self):
        after = {p.relative_to(self.source): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        self.assertEqual(after, self.before, 'Recovery must never edit the original evidence')

    def test_recovered_copy_retains_target_miss_and_records_provenance(self):
        self.invoke()
        meta = json.loads((self.target / 'metadata.json').read_text())
        self.assertEqual((meta['exit_code'], meta['status'], meta['collection_valid']), (99, 'thresholds_failed', True))
        self.assertEqual(meta['log_recovery']['raw_sha256'], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual((self.target / 'request-events.jsonl').read_bytes(), self.before[Path('request-events.jsonl')])
        self.assertEqual((self.target / 'pod-logs/uid.log').read_text(),
                         '2026-11-10T12:00:01Z recovered\n2026-11-10T12:00:02Z saved\n')
        mapping = json.loads((self.series / 'log-recovery.json').read_text())
        self.assertEqual(mapping['runs'], {self.source.name: self.target.name})

    def test_partial_cri_record_is_rejected_before_copy(self):
        with self.assertRaisesRegex(ValueError, 'Partial CRI'):
            self.invoke(raw=b'2026-11-10T12:00:01Z stdout P unfinished\n')
        self.assertFalse(self.target.exists())
        self.assertFalse((self.series / 'log-recovery.json').exists())

    def test_overlapping_stream_is_not_merged_or_accepted(self):
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.invoke(raw=b'2026-11-10T12:00:02Z stdout F duplicate\n')
        self.assertEqual((self.target / 'pod-logs/uid.log').read_bytes(), self.before[Path('pod-logs/uid.log')])
        self.assertFalse((self.series / 'log-recovery.json').exists())

    def test_invalid_reconciliation_does_not_publish_recovery_mapping(self):
        with self.assertRaisesRegex(ValueError, 'missing requests'):
            self.invoke(report=dict(valid=False, errors=['missing requests']))
        meta = json.loads((self.target / 'metadata.json').read_text())
        self.assertFalse(meta['collection_valid'])
        self.assertNotIn('log_recovery', meta)
        self.assertFalse((self.series / 'log-recovery.json').exists())

    def test_existing_recovered_folder_is_not_overwritten(self):
        self.target.mkdir()
        marker = self.target / 'keep'
        marker.write_bytes(b'previous recovery')
        with self.assertRaises(FileExistsError):
            self.invoke()
        self.assertEqual(marker.read_bytes(), b'previous recovery')
        self.assertEqual(list(self.target.iterdir()), [marker])

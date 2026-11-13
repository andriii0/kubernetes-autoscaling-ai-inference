import unittest
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from bench import run_peak12_comparison as driver


class ComparisonReviewTests(unittest.TestCase):
    def fixed_three(self, counts):
        return {
            'metadata': {'mode': 'fixed-3', 'initial_identity': [
                {'pod_uid': uid} for uid in ('a', 'b', 'c')
            ]},
            'check': {'distribution': {'pods': {
                uid: {'completed': count} for uid, count in counts.items()
            }}},
        }

    def test_verified_preliminary_distribution_is_adapted_without_mutation(self):
        data = self.fixed_three({'a': 147, 'b': 155, 'c': 155})
        result = driver.comparison_input(data)
        self.assertTrue(result['check']['distribution']['all_pods_active'])
        self.assertNotIn('all_pods_active', data['check']['distribution'])
        self.assertNotIn('protocol_version', data['metadata'])

    def test_missing_or_inactive_initial_pod_is_not_accepted(self):
        for counts in ({'a': 1, 'b': 1}, {'a': 1, 'b': 1, 'c': 0},
                       {'a': 1, 'b': 1, 'other': 1}):
            with self.subTest(counts=counts):
                with self.assertRaisesRegex(ValueError, 'traffic on each'):
                    driver.comparison_input(self.fixed_three(counts))

    def test_target_miss_continues_but_incomplete_evidence_explains_why(self):
        result = dict(data_valid=True, duration_complete=True, unfinished=0,
                      dropped=0, overall='fail', limitations=[])
        driver.require_assessable(result)
        with self.assertRaisesRegex(ValueError, 'post-load phase was incomplete; dropped=2'):
            driver.require_assessable({**result, 'duration_complete': False, 'dropped': 2})


class SavedComparisonContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / 'run'
        (self.folder / 'inputs').mkdir(parents=True)
        (self.root / 'bench').mkdir()
        self.source = self.root / 'bench/runner.py'
        self.source.write_bytes(b'original')
        (self.folder / 'inputs/runner.py').write_bytes(b'original')
        self.digest = hashlib.sha256(b'original').hexdigest()
        self.check = dict(valid=True, warnings=[], errors=[])
        (self.folder / 'collection-check.json').write_text(json.dumps(self.check))
        self.meta = dict(
            exit_code=99, collector_exit_code=0, errors=[], warnings=[], collection_valid=True,
            mode='autoscaling', profile='burst', rate=12, low_rate=2, duration_seconds=782,
            recovery={'successful': True}, source_sha256={'runner.py': self.digest},
            initial_identity={'image_id': 'image'},
            runtime_context=dict(models={'a': {'digest': 'model'}}, docker_limits={'cpus': 8},
                                 minikube_profile={'Config': {'CPUs': 8, 'Memory': 12000, 'Driver': 'docker'}}))
        self.assessed = dict(data_valid=True, duration_complete=True, unfinished=0, dropped=0,
                             overall='fail', limitations=[], primary={'p95_ms': 6000})
        for target, options in (
            ('ROOT', {'new': self.root}),
            ('load_results', {'return_value': {'metadata': self.meta, 'check': self.check}}),
            ('assessment', {'return_value': self.assessed}),
            ('phase_results', {'return_value': []}),
            ('primary_resources', {'return_value': {}}),
        ):
            patcher = patch.object(driver, target, **options)
            patcher.start()
            self.addCleanup(patcher.stop)

    def review(self, common=None, versions=None):
        return driver.review(self.folder, {'mode': 'autoscaling'}, 99,
                             common if common is not None else {'hashes': {}}, versions)

    def test_valid_target_miss_is_accepted_with_environment(self):
        common = {'hashes': {}}
        self.assertEqual(self.review(common)[0], self.assessed)
        self.assertEqual(common['environment']['models'], ['model'])
        self.assertEqual(common['hashes']['runner.py'], self.digest)

    def test_recovery_collection_settings_and_environment_failures_are_rejected(self):
        cases = [
            ('recovery', {'successful': False}, 'recovery'),
            ('collector_exit_code', 1, 'collection'),
            ('rate', 8, 'settings'),
            ('warnings', ['unexpected'], 'warnings'),
        ]
        for key, value, message in cases:
            with self.subTest(key=key), patch.dict(self.meta, {key: value}):
                with self.assertRaisesRegex(ValueError, message):
                    self.review()
        common = {'hashes': {}}
        self.review(common)
        self.meta['runtime_context']['models']['a']['digest'] = 'different'
        with self.assertRaisesRegex(ValueError, 'runtime settings differ'):
            self.review(common)

    def test_changed_collector_needs_recorded_boundary_but_never_allows_archive_corruption(self):
        self.source.write_bytes(b'new collector')
        updated = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'input mismatch'):
            self.review()
        versions = {'runner.py': [self.digest, updated]}
        self.assertEqual(self.review(versions=versions)[0]['overall'], 'fail')
        (self.folder / 'inputs/runner.py').write_bytes(b'damaged archive')
        with self.assertRaisesRegex(ValueError, 'input mismatch'):
            self.review(versions=versions)

    def test_saved_collection_check_must_match_replay(self):
        (self.folder / 'collection-check.json').write_text('{"valid": false}')
        with self.assertRaisesRegex(ValueError, 'differs from replay'):
            self.review()

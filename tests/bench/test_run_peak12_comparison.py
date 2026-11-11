import unittest

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

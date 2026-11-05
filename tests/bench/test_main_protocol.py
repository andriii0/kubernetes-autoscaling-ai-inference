import argparse
import copy
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import Mock, patch

import analyze
import fixed_replicas
import main_protocol as protocol
import pilot_records
import records
import run_pilot
from tests.bench.fixtures import sample


WORKLOAD = json.loads((Path(__file__).resolve().parents[2] / 'bench/workload.json').read_text())
START = records.timestamp('2026-10-18T12:00:00Z')


def point(second, counter=None):
    at = records.iso_time(START + second)
    result = sample(at)
    status = result['pods']['items'][0]['status']['containerStatuses'][0]
    status['state']['running']['startedAt'] = records.iso_time(START - 60)
    for r in result['resource_usage']:
        r.update(namespace='inference', cpu_timestamp_ms=(START + second) * 1000,
                 memory_timestamp_ms=(START + second) * 1000, restart_count=0,
                 container_start_time_seconds=START - 60,
                 cpu_usage_seconds_total=counter if counter is not None else 10 + second * .05)
    result['resources'] = {'items': [{'metadata': {'name': 'ollama-one'}, 'timestamp': at, 'window': '1s',
        'containers': [{'name': 'ollama', 'usage': {'cpu': '50m'}}]}]}
    return result


def data(profile='steady'):
    duration = 300 if profile == 'steady' else 782
    return {'metadata': {'protocol_version': '1.1', 'mode': 'fixed-1', 'profile': profile,
            'expected_replicas': 1, 'namespace': 'inference', 'container': 'ollama', 'deployment': 'ollama',
            'duration_seconds': duration, 'observer_interval_seconds': 5, 'workload': copy.deepcopy(WORKLOAD),
            'burst_stages': copy.deepcopy(WORKLOAD['burst_stages']) if profile == 'burst' else None,
            'load_process_finished_at_utc': records.iso_time(START + duration + 1),
            'scheduled_profile_finished_at_utc': records.iso_time(START + duration + 1),
            'phases': [{'phase': 'post_load'}]},
            'check': {'valid': True, 'errors': [], 'counts': {'completed': 240, 'failed': 0, 'unfinished': 0, 'dropped': 0},
                      'load_window': {'started_at_utc': records.iso_time(START),
                                      'scheduled_end_at_utc': records.iso_time(START + duration)}},
            'events': [], 'cluster': []}


def completed(second, duration=1000, success=True):
    return {'event': 'completed', 'started_at_utc': records.iso_time(START + second),
            'duration_ms': duration, 'outcome': 'success' if success else 'failure',
            'error_category': None if success else 'timeout'}


class PreparationTests(unittest.TestCase):
    def test_every_matrix_cell_accepts_frozen_settings_and_rejects_mismatch(self):
        self.assertEqual(len(protocol.matrix()), 18)
        self.assertEqual(len({(r['mode'], r['profile'], r['repetition']) for r in protocol.matrix()}), 18)
        for row in protocol.matrix():
            args = argparse.Namespace(**row, protocol_version='1.1', actual_order=row['planned_order'], replaces_run=None,
                rate=8, low_rate=2, observer_interval=5, idle_seconds=60, warmup_timeout=120,
                post_seconds=300 if row['mode'] == 'autoscaling' else 10, slo_ms=None,
                context='ai-lab', namespace='inference', selector='app=ollama', deployment='ollama', container='ollama', service='ollama')
            protocol.validate_arguments(args, WORKLOAD, 300 if row['profile'] == 'steady' else 782)
            args.rate = 80
            with self.assertRaisesRegex(ValueError, 'frozen'):
                protocol.validate_arguments(args, WORKLOAD, 300)

    def test_bad_main_arguments_create_no_folder_or_observer(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(run_pilot, 'Observer') as observer:
            folder = Path(temporary) / 'attempt'
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                run_pilot.main(['--base-url', 'http://localhost:1', '--rate', '8', '--run-dir', str(folder),
                                '--protocol-version', '1.1', '--repetition', '1', '--planned-order', '2', '--actual-order', '1'])
            self.assertFalse(folder.exists())
            observer.assert_not_called()

    def test_ambient_main_and_k6_overrides_are_removed(self):
        args = argparse.Namespace(base_url='http://localhost', rate=8, duration='300s', slo_ms=None)
        with patch.dict(os.environ, {'MAIN_PROTOCOL': '1.1', 'SLO_MS': '1', 'K6_DURATION': '1s'}):
            env = run_pilot.load_environment(args, 'test')
        self.assertNotIn('MAIN_PROTOCOL', env)
        self.assertNotIn('SLO_MS', env)
        self.assertNotIn('K6_DURATION', env)

    def gate(self, after=START):
        return protocol.QuietState({'pod_uid': 'pod-1'}, 'ollama', after)

    def test_quiet_gate_needs_two_fresh_intervals_after_warmup(self):
        gate = self.gate(START + 1)
        for second in (0, 1, 2):
            self.assertFalse(gate.accept(point(second)))
        self.assertTrue(gate.accept(point(3)))
        gate = self.gate()
        self.assertFalse(gate.accept(point(1)))
        self.assertFalse(gate.accept(point(1)))
        self.assertFalse(gate.accept(point(1)))
        self.assertEqual(gate.consecutive, 0)

    def test_high_cpu_missing_counter_restart_and_gap_reset_gate(self):
        for case in ('high', 'missing', 'restart', 'gap'):
            with self.subTest(case=case):
                gate = self.gate()
                gate.accept(point(0))
                gate.accept(point(1))
                p = point(20 if case == 'gap' else 2)
                r = p['resource_usage'][0]
                if case == 'high': r['cpu_usage_seconds_total'] = 100
                if case == 'missing': r['cpu_timestamp_ms'] = None
                if case == 'restart': r['restart_count'] = 1
                self.assertFalse(gate.accept(p))
                self.assertEqual(gate.consecutive, 0)

    def test_staggered_copies_each_need_two_fresh_intervals_after_warmup(self):
        from tests.bench.fixtures import three_sample
        gate = protocol.QuietState([{'pod_uid': f'pod-{i}'} for i in (1, 2, 3)], 'ollama', START)
        for second in range(0, 31, 5):
            p = three_sample(records.iso_time(START + second))
            for r in p['resource_usage']:
                if r['scope'] != 'container': continue
                shift = (0, 5, 3)[int(r['pod_uid'][-1]) - 1]
                source = ((second + shift) // 10) * 10 - shift
                r.update(cpu_timestamp_ms=(START + source) * 1000, cpu_usage_seconds_total=100 + .05 * source,
                         restart_count=0, container_start_time_seconds=START - 60)
            self.assertEqual(gate.accept(p), second == 30, second)
        self.assertEqual(gate.consecutive, 2)

    def test_cached_copy_cannot_borrow_other_copies_quiet_intervals(self):
        from tests.bench.fixtures import three_sample
        gate = protocol.QuietState([{'pod_uid': f'pod-{i}'} for i in (1, 2, 3)], 'ollama', START)
        for second in range(0, 51, 5):
            p = three_sample(records.iso_time(START + second))
            for r in p['resource_usage']:
                if r['scope'] != 'container': continue
                source = 0 if r['pod_uid'] == 'pod-3' else second
                r.update(cpu_timestamp_ms=(START + source) * 1000, cpu_usage_seconds_total=100 + .05 * source,
                         restart_count=0, container_start_time_seconds=START - 60)
            self.assertFalse(gate.accept(p))
        self.assertEqual(gate.consecutive, 0)

    def test_conflicting_or_backward_source_point_cannot_seed_a_quiet_interval(self):
        for bad_source in (10, 5):
            with self.subTest(bad_source=bad_source):
                gate = self.gate()
                readings = ((0, 0, 10), (5, 5, 11), (10, 10, 12), (15, bad_source, 100),
                            (20, 15, 100.25), (25, 20, 100.5), (30, 25, 100.75))
                for collected, source, counter in readings:
                    p = point(source, counter)
                    p['time'] = records.iso_time(START + collected)
                    self.assertEqual(gate.accept(p), collected == 30, collected)

    def test_hpa_metrics_window_must_exclude_warmup_and_be_low(self):
        gate = self.gate(START + 1)
        for second in (1, 2): gate.accept(point(second))
        p = point(3)
        p['resources']['items'][0]['window'] = '30s'
        self.assertFalse(gate.accept(p, True))
        p = point(4)
        p['resources']['items'][0]['containers'][0]['usage']['cpu'] = '101m'
        self.assertFalse(gate.accept(p, True))
        self.assertTrue(gate.accept(point(5), True))

    def test_gate_timeout_never_starts_load(self):
        collection = Mock(identity={'pod_uid': 'pod-1'}, container='ollama', interval=5)
        with patch.object(protocol.time, 'monotonic', side_effect=[0, 181]):
            with self.assertRaisesRegex(RuntimeError, '180 seconds'):
                protocol.settle(collection, records.iso_time(START))

    def test_model_and_runtime_context_use_independent_sources(self):
        observer = Mock(namespace='inference', context='ai-lab')
        observer.read.return_value = json.dumps({'models': [{'name': WORKLOAD['request']['model'], 'digest': 'model-a'}]})
        docker = Mock(stdout='{"cpu":16,"memory_bytes":32000000000}')
        profile = Mock(stdout='{"valid":[{"Name":"ai-lab","Config":{"CPUs":8,"Memory":12288}}]}')
        with tempfile.TemporaryDirectory() as temporary, patch.object(protocol.subprocess, 'run', side_effect=[docker, profile]):
            result = protocol.runtime_context(observer, point(0)['pods']['items'], Path(temporary), WORKLOAD['request']['model'])
        self.assertEqual(result['models']['pod-1']['digest'], 'model-a')
        self.assertEqual(result['docker_limits']['cpu'], 16)
        self.assertEqual(result['minikube_profile']['Config']['CPUs'], 8)

    def test_recovery_precedes_mode_mutation_and_preserves_samples(self):
        observer = Mock()
        observer.collect.side_effect = [point(0), point(5), point(10)]
        with tempfile.TemporaryDirectory() as temporary, patch.object(protocol.time, 'sleep'), \
                patch('observe.utc_now', return_value=records.iso_time(START)):
            result = protocol.recover(observer, Path(temporary), 'ollama')
            self.assertEqual(len(list(records.read_jsonl(Path(temporary) / 'recovery-observations.jsonl'))), 3)
        self.assertEqual(result['passed_at_utc'], point(10)['time'])
        observer.read.assert_not_called()

    def test_fixed_preparation_checks_conflicts_before_mutation(self):
        observer = Mock(namespace='inference')
        observer.read.return_value = json.dumps({'items': [{'metadata': {'name': 'foreign'},
            'spec': {'scaleTargetRef': {'kind': 'Deployment', 'name': 'ollama'}}}]})
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            protocol.prepare_fixed(observer, 'ollama', 'ollama', 3)
        self.assertEqual(observer.read.call_count, 1)
        observer.collect.assert_not_called()

    def test_main_missing_k6_still_saves_not_assessable_attempt(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(run_pilot.shutil, 'which', return_value=None), \
                patch.object(protocol, 'source_revision', return_value={'commit': 'local-test-fixture', 'dirty': False}), redirect_stderr(io.StringIO()):
            folder = Path(temporary) / 'attempt'
            code = run_pilot.main(['--base-url', 'http://localhost:1', '--rate', '8', '--run-dir', str(folder),
                '--protocol-version', '1.1', '--repetition', '1', '--planned-order', '1', '--actual-order', '1'])
            self.assertEqual(code, 1)
            result = json.loads((folder / 'assessment.json').read_text())
            self.assertFalse(result['data_valid'])
            self.assertEqual(result['overall'], 'not_assessable')


class AssessmentTests(unittest.TestCase):
    def test_burst_peak_uses_start_time_and_retains_late_completions(self):
        d = data('burst')
        d['events'] = [completed(120.999, 10), completed(121, 6000), completed(420.999, 6000), completed(421, 10)]
        peak = next(p for p in analyze.phase_results(d) if p['name'] == 'peak')
        self.assertEqual(peak['completed'], 2)
        result = analyze.assessment(d)
        self.assertFalse(result['primary_p95_pass'])
        self.assertTrue(result['sensitivity_p95_pass'])
        self.assertEqual(result['overall'], 'fail')

    def test_unrounded_error_boundaries_and_whole_run_target(self):
        for failed, expected in ((2, True), (3, False)):
            d = data()
            d['events'] = [completed(i, success=i >= failed) for i in range(240)]
            d['check']['counts']['failed'] = failed
            r = analyze.assessment(d)
            self.assertIs(r['primary_errors_pass'], expected)
            self.assertEqual(r['overall'], 'pass' if expected else 'fail')
        d = data('burst')
        d['events'] = [completed(121)]
        d['check']['counts'].update(failed=4, completed=240)
        self.assertEqual(analyze.assessment(d)['overall'], 'fail')

    def test_empty_latency_drops_invalid_data_and_early_stop_cannot_pass(self):
        d = data()
        d['events'] = [completed(1, success=False)]
        self.assertEqual(analyze.assessment(d)['primary_p95_pass'], 'not_assessable')
        for change in ('drops', 'unfinished', 'early'):
            d = data()
            d['events'] = [completed(1)]
            if change == 'drops': d['check']['counts']['dropped'] = 1
            if change == 'unfinished':
                d['check']['counts']['unfinished'] = 1
                d['check']['valid'] = False  # Existing reconcile owns this rejection.
            if change == 'early': d['metadata']['phases'] = []
            self.assertEqual(analyze.assessment(d)['overall'], 'not_assessable')

    def test_resource_gaps_keep_request_verdict_and_oom_is_retained(self):
        d = data()
        d['events'] = [completed(1)]
        p = point(1)
        p['errors'] = [{'category': 'missing_resource'}]
        p['resource_usage'] = []
        d['cluster'] = [p]
        self.assertEqual(analyze.assessment(d)['overall'], 'pass')
        status = p['pods']['items'][0]['status']['containerStatuses'][0]
        status['lastState'] = {'terminated': {'reason': 'OOMKilled', 'exitCode': 137}}
        d['check']['valid'] = False
        r = analyze.assessment(d)
        self.assertEqual(r['system_outcomes'][0]['termination']['reason'], 'OOMKilled')
        self.assertEqual(r['overall'], 'not_assessable')

    def test_fixed_timeout_status_mismatch_is_not_missing_traffic(self):
        from tests.bench.fixtures import FixedReplicaFixture
        host = FixedReplicaFixture()
        host.setUp()
        self.addCleanup(host.doCleanups)
        metadata = host.logs()
        metadata['protocol_version'] = '1.1'
        result = fixed_replicas.distribution(host.folder, metadata, {'completed': 1}, [{'http_status': 0}])
        self.assertTrue(result['all_pods_active'])
        (host.folder / 'pod-logs/pod-2.log').write_text('')
        result = fixed_replicas.distribution(host.folder, metadata, {'completed': 1}, [{'http_status': 0}])
        self.assertFalse(result['all_pods_active'])
        self.assertEqual(result['pods']['pod-2']['completed'], 0)

    def test_truncated_cluster_tail_keeps_readable_oom_evidence(self):
        d = data()
        d['check'].update(valid=False, load_window=None, errors=['cluster JSON is truncated'])
        p = point(1)
        p['pods']['items'][0]['status']['containerStatuses'][0]['state'] = {
            'terminated': {'reason': 'OOMKilled', 'exitCode': 137}}
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / 'cluster.jsonl').write_text(json.dumps(p) + '\n{"truncated":')
            result = analyze.save_assessment(folder, d['metadata'], d['check'])
        self.assertEqual(result['overall'], 'not_assessable')
        self.assertEqual(result['system_outcomes'][0]['termination']['reason'], 'OOMKilled')


class ResourceTests(unittest.TestCase):
    def resources(self, points):
        d = data()
        d['check']['load_window']['scheduled_end_at_utc'] = records.iso_time(START + 10)
        d['cluster'] = points
        return analyze.primary_resources(d)

    def test_counter_integration_clips_boundaries_and_deduplicates_source_polls(self):
        points = [point(t, 100 + 2 * t) for t in (-2, 2, 2, 8, 12)]
        points[2]['time'] = records.iso_time(START + 3)
        result = self.resources(points)
        r = result['instances'][0]
        self.assertEqual(r['cpu_core_seconds_estimate'], 20)
        self.assertEqual(r['cpu_covered_seconds'], 10)
        self.assertTrue(r['cpu_full_coverage'])
        self.assertEqual(result['application_cpu_core_seconds_estimate'], 20)
        self.assertEqual(r['memory_samples'], 2)
        self.assertEqual(len(result['nodes']), 1)

    def test_missing_counter_reset_and_unknown_lifetime_keep_incomplete_totals(self):
        for defect in ('missing', 'reset', 'lifetime', 'scrape'):
            with self.subTest(defect=defect):
                points = [point(t, 100 + t) for t in (0, 5, 10)]
                if defect == 'missing': points[1]['resource_usage'] = []
                if defect == 'reset': points[1]['resource_usage'][0]['cpu_usage_seconds_total'] = 1
                if defect == 'lifetime':
                    for p in points: p['pods']['items'][0]['status']['containerStatuses'][0]['state']['running'] = {}
                if defect == 'scrape': points[1]['errors'] = [{'source': 'kubelet', 'message': 'failed'}]
                result = self.resources(points)
                self.assertIsNone(result['application_cpu_core_seconds_estimate'])

    def test_backward_source_clock_cannot_double_count_a_full_primary_window(self):
        d = data()
        for collected in range(0, 315, 5):
            source = collected if collected < 10 else collected - 8
            p = point(collected, 100 + source)
            for r in p['resource_usage']:
                r['cpu_timestamp_ms'] = (START + source) * 1000
            d['cluster'].append(p)
        result = analyze.primary_resources(d)
        self.assertIsNone(result['application_cpu_core_seconds_estimate'])
        for r in result['instances'] + result['nodes']:
            self.assertEqual(r['cpu_core_seconds_estimate'], 298)
            self.assertEqual(r['cpu_covered_seconds'], 298)
            self.assertFalse(r['cpu_full_coverage'])

    def test_backward_source_clock_after_missing_poll_does_not_reuse_coverage(self):
        points = [point(t, 100 + t) for t in (0, 5, 6, 7, 8, 10, 12)]
        points[2]['resource_usage'] = []
        for p, source in zip(points[3:], (2, 7, 10, 12)):
            for r in p['resource_usage']:
                r.update(cpu_timestamp_ms=(START + source) * 1000, cpu_usage_seconds_total=100 + source)
        result = self.resources(points)
        self.assertIsNone(result['application_cpu_core_seconds_estimate'])
        self.assertEqual(result['instances'][0]['cpu_core_seconds_estimate'], 8)
        self.assertEqual(result['instances'][0]['cpu_covered_seconds'], 8)

    def test_fixed_missing_resource_counter_is_separate_from_state_validation(self):
        p = point(0)
        p['resource_usage'] = []
        p['errors'] = [{'category': 'missing_resource'}]
        with self.assertRaises(ValueError): records.pilot_identity(p)
        self.assertEqual(records.pilot_identity(p, allow_resource_gaps=True)['pod_uid'], 'pod-1')
        p['errors'] = [{'source': 'pods', 'message': 'API failed'}]
        with self.assertRaises(ValueError): records.pilot_identity(p, allow_resource_gaps=True)

    def test_asynchronous_instances_can_sum_only_complete_interval_totals(self):
        from tests.bench.fixtures import three_sample
        points = []
        for second in (-2, 5, 12):
            p = three_sample(records.iso_time(START + second))
            for pod in p['pods']['items']:
                pod['status']['containerStatuses'][0]['state']['running']['startedAt'] = records.iso_time(START - 60)
            for r in p['resource_usage']:
                if r['scope'] == 'node': continue
                index = int(r['pod_uid'][-1])
                clock = second + (index - 2) * .5
                r.update(restart_count=0, container_start_time_seconds=START - 60,
                    cpu_timestamp_ms=(START + clock) * 1000, cpu_usage_seconds_total=100 + clock * index)
            points.append(p)
        result = self.resources(points)
        self.assertAlmostEqual(result['application_cpu_core_seconds_estimate'], 60)
        self.assertEqual(len(result['instances']), 3)
        self.assertNotIn('application_peak_memory_mib', result)


class MainLifecycleTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this local integration check')
    def test_actual_k6_primary_target_failure_retains_valid_collection(self):
        from tests.bench.fixtures import AutoscalingFixture
        host = AutoscalingFixture()
        self.addCleanup(host.doCleanups)
        # Deliberately impossible fixture threshold; never a project SLO.
        folder, code = host.exercise(profile='steady', main=True, latency_target=.000001)
        self.assertEqual(code, 99)
        result = json.loads((folder / 'assessment.json').read_text())
        self.assertTrue(result['data_valid'])
        self.assertFalse(result['primary_p95_pass'])
        self.assertEqual(result['overall'], 'fail')

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this local integration check')
    def test_main_fixed_one_and_three_with_both_profiles(self):
        from tests.bench.fixtures import FixedLauncherFixture
        for replicas in (1, 3):
            for profile in ('steady', 'burst'):
                with self.subTest(replicas=replicas, profile=profile):
                    host = FixedLauncherFixture()
                    self.addCleanup(host.doCleanups)
                    folder, code, _ = host.run_fixture(main=True, replicas=replicas, profile=profile)
                    result = json.loads((folder / 'assessment.json').read_text())
                    self.assertEqual(code, 0, (folder / 'metadata.json').read_text())
                    self.assertEqual(result['overall'], 'pass', result)
                    self.assertEqual(result['scaling_observed'], 'not_applicable')

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this local integration check')
    def test_main_fixed_one_without_measured_pod_traffic_is_not_assessable(self):
        from tests.bench.fixtures import FixedLauncherFixture
        host = FixedLauncherFixture()
        self.addCleanup(host.doCleanups)
        folder, code, _ = host.run_fixture(main=True, replicas=1)
        self.assertEqual(code, 0, (folder / 'collection-check.json').read_text())
        log = folder / 'pod-logs/pod-1.log'
        warmup = log.read_text().splitlines()[0]
        for evidence in ('', warmup):
            with self.subTest(evidence=evidence):
                log.write_text(evidence, encoding='utf-8')
                data = analyze.load_results(folder)
                self.assertFalse(data['check']['valid'])
                self.assertIn('no measured generation traffic in the fixed-one pod log', data['check']['errors'])
                self.assertEqual(analyze.assessment(data)['overall'], 'not_assessable')

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this local integration check')
    def test_main_autoscaling_steady_and_burst_reuse_existing_lifecycle(self):
        from tests.bench.fixtures import AutoscalingFixture
        for profile in ('steady', 'burst'):
            with self.subTest(profile=profile):
                host = AutoscalingFixture()
                self.addCleanup(host.doCleanups)
                folder, code = host.exercise(profile=profile, main=True)
                check = json.loads((folder / 'collection-check.json').read_text())
                self.assertEqual(code, 0, check)
                self.assertFalse(any('input' in w for w in check['warnings']), check)
                metadata = json.loads((folder / 'metadata.json').read_text())
                self.assertTrue({'main_protocol.py', 'analyze.py', 'fixed_replicas.py', 'autoscaling.py', 'hpa.yaml'}
                                <= set(metadata['source_sha256']))
                manifest = folder / 'inputs' / 'hpa.yaml'
                manifest.write_bytes(manifest.read_bytes() + b'\n# changed archive\n')
                archive_check = pilot_records.reconcile(folder, metadata)
                self.assertTrue(archive_check['valid'], archive_check)
                self.assertIn('executable input changed: hpa.yaml', archive_check['warnings'])
                del metadata['source_sha256']['hpa.yaml']
                self.assertIn('incomplete executable input hashes', pilot_records.reconcile(folder, metadata)['warnings'])
                result = json.loads((folder / 'assessment.json').read_text())
                self.assertEqual(result['overall'], 'pass', result)
                self.assertTrue(result['duration_complete'])
                self.assertEqual(result['unfinished'], 0)
                output = folder / 'main-analysis'
                self.assertEqual(analyze.main([str(folder), '--output-dir', str(output), '--no-plots']), 0)
                self.assertTrue((output / 'primary-resources.json').is_file())


if __name__ == '__main__':
    unittest.main()

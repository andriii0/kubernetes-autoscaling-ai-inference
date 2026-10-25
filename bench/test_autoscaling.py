import copy
import json
import shutil
from datetime import datetime, timedelta, timezone
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import analyze
import autoscaling
import pilot_records
import run_pilot
from test_fixed_replicas import three_sample
from test_pilot_records import sample
import test_pilot_records


def hpa():
    return {'metadata': {'name': 'ollama'}, 'spec': {'scaleTargetRef': {'kind': 'Deployment', 'name': 'ollama'},
            'minReplicas': 1, 'maxReplicas': 3}, 'status': {'currentReplicas': 1, 'desiredReplicas': 1,
            'currentMetrics': [{'type': 'Resource', 'resource': {'name': 'cpu', 'current': {'averageUtilization': 2}}}],
            'conditions': [{'type': 'ScalingActive', 'status': 'True'}]}}


class DynamicStateTests(unittest.TestCase):
    def state(self):
        s = sample()
        i = pilot_records.pilot_identity(s)
        state = autoscaling.State('ollama', 'ollama', autoscaling.configuration(s['deployments']['items'][0]), i['image_id'])
        state.identities[i['pod_uid']] = (i['container_id'], i['restart_count'], i['image_id'])
        state.hpa_spec = hpa()['spec']
        return state

    def test_dynamic_growth_pending_metrics_and_deletion_are_not_fixed_mode(self):
        state = self.state()
        for count in (1, 2, 3, 1):
            current = three_sample()
            current['pods']['items'] = current['pods']['items'][:count]
            current['deployments']['items'][0]['spec']['replicas'] = count
            current['hpa']['items'] = [hpa()]
            state.accept(current)
        current = three_sample()
        current['hpa']['items'] = [hpa()]
        new = current['pods']['items'][1]
        new['status'].update(phase='Pending', containerStatuses=[])
        current['errors'] = [{'category': 'missing_resource', 'source': 'kubelet', 'message': 'absent counter'}]
        state.accept(current)
        new['metadata']['deletionTimestamp'] = current['time']
        state.accept(current)
        with self.assertRaises(ValueError):
            pilot_records.pilot_identity(current, replicas=3)

    def test_restart_api_failure_and_configuration_change_fail(self):
        for case in ('restart', 'api', 'template', 'hpa', 'image', 'replicas', 'missing-hpa'):
            with self.subTest(case=case):
                state = self.state()
                current = sample()
                if case == 'restart': current['pods']['items'][0]['status']['containerStatuses'][0]['restartCount'] += 1
                if case == 'api': current['errors'] = [{'source': 'pods', 'message': 'connection refused'}]
                if case == 'template': current['deployments']['items'][0]['spec']['selector']['matchLabels']['app'] = 'other'
                if case == 'hpa':
                    current['hpa']['items'] = [hpa()]
                    current['hpa']['items'][0]['spec']['maxReplicas'] = 5
                if case == 'image': current['pods']['items'][0]['status']['containerStatuses'][0]['imageID'] = 'wrong'
                if case == 'replicas': current['deployments']['items'][0]['spec']['replicas'] = 4
                if case == 'missing-hpa': state.hpa_required = True
                with self.assertRaises(ValueError):
                    state.accept(current)

    def test_missing_cluster_state_and_deployment_have_explicit_errors(self):
        for key in ('pods', 'deployments', 'hpa'):
            with self.subTest(key=key):
                current = sample()
                current[key] = None
                with self.assertRaisesRegex(ValueError, 'required cluster state is missing'):
                    self.state().accept(current)
        current = sample()
        current['deployments']['items'] = []
        with self.assertRaisesRegex(ValueError, 'Deployment is missing'):
            self.state().accept(current)

    def test_hpa_readiness_needs_numeric_active_and_one_nonterminating_pod(self):
        current = sample()
        current['hpa']['items'] = [hpa()]
        self.assertTrue(autoscaling.hpa_ready(current, 'ollama'))
        for case in ('unknown', 'inactive', 'terminating', 'two-desired'):
            broken = copy.deepcopy(current)
            status = broken['hpa']['items'][0]['status']
            if case == 'unknown': status['currentMetrics'] = []
            if case == 'inactive': status['conditions'][0]['status'] = 'False'
            if case == 'terminating': broken['pods']['items'][0]['metadata']['deletionTimestamp'] = broken['time']
            if case == 'two-desired': status['desiredReplicas'] = 2
            self.assertFalse(autoscaling.hpa_ready(broken, 'ollama'), case)


class LogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.observer = Mock(context='ai-lab', namespace='inference')
        self.logs = autoscaling.Logs(self.observer, self.folder, 'ollama')
        self.addCleanup(self.logs.stop)

    def test_deleted_copy_keeps_file_and_running_copy_process_is_stopped(self):
        first, second = Mock(), Mock()
        first.poll.return_value = None
        second.poll.return_value = None
        first.returncode = second.returncode = 0
        with patch.object(autoscaling.subprocess, 'Popen', side_effect=[first, second]):
            self.logs.update(three_sample() | {'pods': {'items': three_sample()['pods']['items'][:2]}})
        path = self.folder / 'pod-logs/pod-1.log'
        with path.open('ab') as output:
            output.write(b'preserved\n')
        current = sample()
        current['pods']['items'] = []
        first.poll.return_value = 0
        self.logs.update(current)
        self.assertEqual(path.read_bytes(), b'preserved\n')
        self.assertTrue(self.logs.records['pod-1']['deleted'])
        self.logs.stop()
        second.terminate.assert_called_once()
        self.assertEqual(path.read_bytes(), b'preserved\n')

    def test_one_shutdown_failure_does_not_skip_other_log_processes(self):
        first, second = Mock(), Mock()
        first.poll.return_value = second.poll.return_value = None
        first.returncode = second.returncode = 0
        first.terminate.side_effect = OSError('process inaccessible')
        with patch.object(autoscaling.subprocess, 'Popen', side_effect=[first, second]):
            current = three_sample()
            current['pods']['items'] = current['pods']['items'][:2]
            self.logs.update(current)
        with self.assertRaisesRegex(RuntimeError, 'shutdown failed'):
            self.logs.stop()
        second.terminate.assert_called_once()
        first.kill.assert_called_once()
        first.poll.return_value = second.poll.return_value = 0

    def test_unexpected_stream_exit_and_deleted_stream_error_are_failures(self):
        process = Mock()
        process.poll.return_value = None
        process.returncode = 1
        with patch.object(autoscaling.subprocess, 'Popen', return_value=process):
            self.logs.update(sample())
        process.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, 'unexpectedly'):
            self.logs.update(sample())
        self.assertFalse(json.loads((self.folder / 'log-coverage.json').read_text())['pod-1']['complete'])

    def test_stream_failure_after_last_update_is_rejected_at_stop(self):
        for code in (0, 1):
            with self.subTest(code=code):
                folder = self.folder / f'late-{code}'
                folder.mkdir()
                logs = autoscaling.Logs(self.observer, folder, 'ollama')
                self.addCleanup(logs.stop)
                process = Mock(returncode=code)
                process.poll.return_value = None
                with patch.object(autoscaling.subprocess, 'Popen', return_value=process):
                    logs.update(sample())
                process.poll.return_value = code
                with self.assertRaisesRegex(RuntimeError, 'ended unexpectedly'):
                    logs.stop()
                saved = json.loads((folder / 'log-coverage.json').read_text())['pod-1']
                self.assertFalse(saved['complete'])
                self.assertEqual(saved['exit_code'], code)
                self.assertNotIn('stopped_by_collector', saved)
                process.terminate.assert_not_called()

    def test_requested_nonzero_stop_and_observed_termination_are_complete(self):
        for kind in ('requested', 'terminated'):
            with self.subTest(kind=kind):
                folder = self.folder / kind
                folder.mkdir()
                logs = autoscaling.Logs(self.observer, folder, 'ollama')
                self.addCleanup(logs.stop)
                process = Mock(returncode=1 if kind == 'requested' else 0)
                process.poll.return_value = None
                with patch.object(autoscaling.subprocess, 'Popen', return_value=process):
                    logs.update(sample())
                if kind == 'terminated':
                    current = sample()
                    current['pods']['items'][0]['status']['containerStatuses'][0]['state'] = {'terminated': {}}
                    process.poll.return_value = 0
                    logs.update(current)
                logs.stop()
                record = logs.records['pod-1']
                self.assertTrue(record['complete'])
                self.assertTrue(autoscaling.complete_log_exit(record))

    def test_missing_file_is_not_zero_traffic_and_empty_new_pod_is_allowed(self):
        records = {f'pod-{i}': {'complete': True, 'pod_name': f'ollama-{i}',
                               'exit_code': 1, 'stopped_by_collector': True} for i in (1, 2, 3)}
        (self.folder / 'log-coverage.json').write_text(json.dumps(records))
        for uid in records:
            (self.folder / 'pod-logs' / f'{uid}.log').write_text('')
        metadata = {'container': 'ollama', 'load_process_started_at_utc': '2026-10-18T12:00:00Z'}
        result = autoscaling.log_summary(self.folder, metadata, [three_sample()])
        self.assertTrue(result['complete'])
        self.assertIsNone(result['pods']['pod-2']['first_observed_http_response_at_utc'])
        (self.folder / 'pod-logs/pod-2.log').unlink()
        with self.assertRaises(OSError):
            autoscaling.log_summary(self.folder, metadata, [three_sample()])


class ReconciliationTests(unittest.TestCase):
    def fixture(self):
        fixture = test_pilot_records.RecordTests('test_valid_collection_and_missing_optional_values')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.metadata.update(mode='autoscaling', expected_replicas=None, namespace='inference',
                                deployment_snapshot=sample()['deployments']['items'][0], hpa_spec=hpa()['spec'], profile='steady')
        (fixture.folder / 'service-route.json').write_text(json.dumps({'service': {'spec': {'selector': {'app': 'ollama'},
            'ports': [{'port': 11434, 'targetPort': 11434}]}}, 'endpoint_slices': {'items': [{'endpoints': [
                {'conditions': {'ready': True}, 'targetRef': {'kind': 'Pod', 'uid': 'pod-1'}}]}]}}))
        (fixture.folder / 'pod-logs').mkdir()
        (fixture.folder / 'pod-logs/pod-1.log').write_text('')
        (fixture.folder / 'log-coverage.json').write_text(json.dumps({'pod-1': {'pod_name': 'ollama-one', 'complete': True,
            'exit_code': 1, 'stopped_by_collector': True}}))
        return fixture

    def test_valid_requests_do_not_require_matching_server_statuses_after_timeout(self):
        f = self.fixture()
        f.completed.update(outcome='failure', error_category='timeout', http_status=0)
        f.remove_latency('successful_latency_ms')
        f.points[-1]['data']['value'] = 1
        f.summary['metrics']['inference_errors'] = {'passes': 1, 'fails': 0}
        (f.folder / 'pod-logs/pod-1.log').write_text('2026-10-18T12:00:04Z [GIN] | 200 | 3s | ip | POST "/api/generate"\n')
        report = f.check()
        self.assertTrue(report['valid'], report)
        self.assertEqual(report['counts']['failed'], 1)
        self.assertEqual(report['logs']['pods']['pod-1']['http_responses_after_load_start'], 1)
        f.summary['metrics']['requests_completed']['count'] = 5
        self.assertFalse(f.check()['valid'])

    def test_api_failure_and_log_coverage_failure_invalidate_saved_run(self):
        f = self.fixture()
        self.assertTrue(f.check()['valid'])
        f.samples[0]['errors'] = [{'source': 'pods', 'message': 'refused'}]
        self.assertFalse(f.check()['valid'])
        f.samples[0]['errors'] = []
        (f.folder / 'log-coverage.json').write_text('{}')
        self.assertFalse(f.check()['valid'])

    def test_replay_rejects_contradictory_stream_exit_evidence(self):
        f = self.fixture()
        for record, valid in (
            ({'exit_code': 1, 'stopped_by_collector': True}, True),
            ({'exit_code': 0, 'deleted': True}, True),
            ({'exit_code': 0, 'container_terminated': True}, True),
            ({'exit_code': 1, 'deleted': True}, False),
            ({'exit_code': 1, 'deleted': False}, False),
            ({'exit_code': 0, 'deleted': False}, False),
            ({'exit_code': None, 'stopped_by_collector': True}, False),
        ):
            with self.subTest(record=record):
                coverage = {'pod-1': {'pod_name': 'ollama-one', 'complete': True, **record}}
                (f.folder / 'log-coverage.json').write_text(json.dumps(coverage))
                report = f.check()
                self.assertEqual(report['valid'], valid, report)
                if not valid:
                    self.assertIn('incomplete pod log: pod-1', report['errors'])

    def test_no_scaling_is_reported_without_inventing_success(self):
        f = self.fixture()
        report = f.check()
        f.metadata.update(phases=[], burst_stages=[{'name': 'low', 'seconds': 1, 'target': 'low'}])
        data = {'metadata': f.metadata, 'events': f.events, 'check': report, 'cluster': f.samples}
        detail = analyze.scaling_details(data)
        self.assertFalse(detail['growth_observed'])
        self.assertFalse(detail['reduction_observed'])
        self.assertIsNone(detail['first_growth_seconds'])
        self.assertEqual(detail['stages'][0]['successful'], 1)
        self.assertEqual(detail['stages'][0]['p95_ms'], 500)

    def test_missing_pod_count_cannot_confirm_scale_down(self):
        f = self.fixture()
        report = f.check()
        f.metadata.update(phases=[], burst_stages=[{'name': 'low', 'seconds': 1, 'target': 'low'}])
        known = three_sample('2026-10-18T12:00:01Z')
        known['pods']['items'] = known['pods']['items'][:2]
        known['hpa']['items'] = [hpa()]
        known['hpa']['items'][0]['status'].update(currentReplicas=2, desiredReplicas=2)
        missing = sample('2026-10-18T12:00:02Z')
        missing['pods'] = None
        missing['hpa']['items'] = [hpa()]
        data = {'metadata': f.metadata, 'events': f.events, 'check': report, 'cluster': [known, missing]}
        detail = analyze.scaling_details(data)
        self.assertTrue(detail['growth_observed'])
        self.assertFalse(detail['reduction_observed'])
        self.assertIsNone(detail['changes'][-1]['running_matches_seconds'])
        self.assertIsNone(detail['pods']['pod-2']['first_absent_at_utc'])

    def test_phase_assignment_keeps_one_millisecond_boundary_requests(self):
        f = self.fixture()
        report = f.check()
        f.metadata.update(phases=[], burst_stages=[{'name': 'low', 'seconds': 1, 'target': 'low'}])
        first, last = copy.deepcopy(f.completed), copy.deepcopy(f.completed)
        first['started_at_utc'] = '2026-10-18T12:00:00.999Z'
        last['started_at_utc'] = '2026-10-18T12:00:02.001Z'
        data = {'metadata': f.metadata, 'events': [first, last], 'check': report, 'cluster': f.samples}
        self.assertEqual(analyze.scaling_details(data)['stages'][0]['completed'], 2)

    def test_autoscaling_requires_saved_service_route(self):
        f = self.fixture()
        self.assertTrue(f.check()['valid'])
        (f.folder / 'service-route.json').unlink()
        self.assertFalse(f.check()['valid'])

    def test_dynamic_resource_series_include_new_pods_without_summing(self):
        f = self.fixture()
        f.check()
        data = {'metadata': f.metadata, 'cluster': [three_sample()], 'check': {'load_window': {
            'started_at_utc': '2026-10-18T11:59:59Z', 'client_drain_end_at_utc': '2026-10-18T12:00:01Z'}}}
        self.assertEqual(len(analyze.identities(data)), 3)
        self.assertIsNone(analyze.resource_points(data)[0]['cpu'])
        self.assertEqual(analyze.resource_points(data, 'pod-2')[0]['cpu'], 2)
        self.assertEqual(len(analyze.replica_resources(data)), 3)


class LauncherTests(unittest.TestCase):
    def test_conflicting_flags_do_not_create_directory_or_change_cluster(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'run'
            base = ['--base-url', 'http://localhost:1', '--rate', '8', '--run-dir', str(folder)]
            with patch.object(run_pilot, 'Observer') as observer:
                for flags in (['--mode', 'autoscaling', '--replicas', '3'], ['--mode', 'autoscaling', '--profile', 'burst', '--replicas', '1'],
                              ['--profile', 'burst', '--duration', '2m'], ['--mode', 'fixed-1', '--replicas', '3']):
                    with self.assertRaises(SystemExit):
                        run_pilot.main(base + flags)
                    self.assertFalse(folder.exists())
                observer.assert_not_called()

    def test_burst_shared_stages_and_k6_deadline_use_782_seconds(self):
        workload = json.loads((Path(run_pilot.__file__).parent / 'workload.json').read_text())
        self.assertEqual(sum(s['seconds'] for s in workload['burst_stages']), 782)
        with tempfile.TemporaryDirectory() as temporary:
            process = Mock(returncode=0)
            process.poll.side_effect = [None, 0, 0]
            metadata = {'duration_seconds': 782, 'workload': workload}
            with patch.object(run_pilot.subprocess, 'Popen', return_value=process), \
                 patch.object(run_pilot.time, 'monotonic', side_effect=[0, 200]):
                self.assertEqual(run_pilot.run_load([], {}, Path(temporary), Mock(), metadata), 0)
                process.terminate.assert_not_called()
            (Path(temporary) / 'timeout').mkdir()
            process.poll.side_effect = [None, None, None]
            metadata = {'duration_seconds': 782, 'workload': workload}
            with patch.object(run_pilot.subprocess, 'Popen', return_value=process), \
                 patch.object(run_pilot.time, 'monotonic', side_effect=[0, 878]):
                with self.assertRaisesRegex(RuntimeError, 'exceeded'):
                    run_pilot.run_load([], {}, Path(temporary) / 'timeout', Mock(), metadata)
                process.terminate.assert_called_once()

    def test_hpa_readiness_timeout_preserves_reason(self):
        session = autoscaling.Session(Mock(context='ai-lab', namespace='inference'), Path('.'), 'ollama', 'ollama', 'ollama', Path('hpa.yaml'))
        session.state = DynamicStateTests().state()
        collection = Mock(lock=run_pilot.threading.RLock(), interval=5)
        with tempfile.TemporaryDirectory() as temporary:
            session.folder = Path(temporary)
            with patch.object(session, 'command', side_effect=['applied', json.dumps(hpa())]), \
                 patch.object(autoscaling.time, 'monotonic', side_effect=[0, 301]):
                with self.assertRaisesRegex(RuntimeError, '300 seconds'):
                    session.enable(collection)
                self.assertTrue((session.folder / 'hpa-applied.json').exists())

    def test_restoration_failure_is_recorded_separately(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = autoscaling.Session(Mock(), Path(temporary), 'ollama', 'ollama', 'ollama', Path('hpa.yaml'))
            session.mutated = True
            with patch.object(session, 'command', side_effect=RuntimeError('API down')):
                result = session.restore()
            self.assertFalse(result['successful'])
            self.assertEqual(json.loads((session.folder / 'recovery.json').read_text())['errors'], ['API down'])


class AutoscalingLifecycleTests(unittest.TestCase):
    def exercise(self, interrupt=False, fail_warmup=False, profile="burst", main=False, latency_target=None, startup_delay=0):
        import time
        import shutil
        import test_run_pilot
        fixture = test_run_pilot.PilotLauncherTests('test_real_k6_full_lifecycle_and_complete_evidence')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        captured = fixture.server(fail_warmup=fail_warmup)
        workload_path = Path(run_pilot.__file__).parent / 'workload.json'
        workload = json.loads(workload_path.read_text())
        for stage, seconds in zip(workload['burst_stages'], (.2, .05, .5, .05, .2)):
            stage['seconds'] = seconds
        if main:
            workload["main_protocol"].update(peak_rate=30, steady_seconds=1, observer_interval_seconds=.05, idle_seconds=0, hpa_post_seconds=1)
        if latency_target is not None:
            workload["main_protocol"]["primary_p95_ms"] = latency_target
        original_read, original_copy = Path.read_text, shutil.copyfile

        def read(path, *args, **kwargs):
            if path == workload_path:
                return json.dumps(workload)
            return original_read(path, *args, **kwargs)

        def copy(source, destination, *args, **kwargs):
            if Path(source) == workload_path:
                Path(destination).write_text(json.dumps(workload))
                return destination
            return original_copy(source, destination, *args, **kwargs)

        # Keep fixture timestamps on a precise elapsed clock, even on coarse wall clocks.
        origin = datetime.now(timezone.utc)
        origin_counter = time.perf_counter_ns()

        def observation_time():
            return (origin + timedelta(microseconds=(time.perf_counter_ns() - origin_counter) // 1000)).isoformat()

        class Observer:
            applied = None
            load_samples = 0
            def __init__(self, context, namespace, selector):
                self.context, self.namespace, self.selector = context, namespace, selector
            def collect(self, interval):
                current = sample(observation_time())
                if Observer.applied is not None:
                    # The first request warms the model; later requests are measured traffic.
                    # Advance on collected samples so k6 startup time cannot consume the transition.
                    if len(captured) > 1:
                        Observer.load_samples += 1
                    count = 2 if 1 <= Observer.load_samples <= 3 else 1
                    if count == 2:
                        current = three_sample(current["time"])
                        current['pods']['items'] = current['pods']['items'][:2]
                        current['deployments']['items'][0]['spec']['replicas'] = 2
                    current['hpa']['items'] = [hpa()]
                    current['hpa']['items'][0]['status'].update(currentReplicas=count, desiredReplicas=count)
                return current
            def read(self, *args):
                if 'apply' in args:
                    Observer.applied = time.monotonic()
                    return 'applied'
                if 'delete' in args:
                    Observer.applied = None
                    return 'deleted'
                if 'scale' in args: return 'scaled'
                if 'endpointslices' in args:
                    return json.dumps({'items': [{'endpoints': [{'conditions': {'ready': True}, 'targetRef': {'kind': 'Pod', 'uid': 'pod-1'}}]}]})
                if 'service' in args:
                    return json.dumps({'spec': {'selector': {'app': 'ollama'}, 'ports': [{'port': 11434, 'targetPort': 11434}]}})
                if 'hpa' in args and 'ollama' in args: return json.dumps(hpa())
                kind = next(x for x in ('deployment', 'pods', 'hpa') if x in args)
                return json.dumps(self.collect(5)[{'deployment': 'deployments', 'pods': 'pods', 'hpa': 'hpa'}[kind]])

        class Logs:
            def __init__(self, observer, folder, container):
                self.folder = folder
                self.records = {}
                self.stopped = False
                (folder / 'pod-logs').mkdir()
            def update(self, sample):
                for p in sample['pods']['items']:
                    uid = p['metadata']['uid']
                    self.records[uid] = {'pod_name': p['metadata']['name'], 'complete': True,
                                         'exit_code': 1, 'stopped_by_collector': True}
                    (self.folder / 'pod-logs' / (uid + '.log')).touch()
            def stop(self):
                self.stopped = True
                (self.folder / 'log-coverage.json').write_text(json.dumps(self.records))

        original_load = run_pilot.run_load

        def delayed_load(command, environment, folder, collection, metadata):
            collection.wait(startup_delay)
            return original_load(command, environment, folder, collection, metadata)

        args = fixture.args[:]
        args[args.index('--post-seconds') + 1] = '1'
        index = args.index('--duration')
        del args[index:index+2]
        args += ['--mode', 'autoscaling', '--profile', profile, '--rate', '30', '--observer-interval', '.05']
        if profile == 'steady':
            args += ['--duration', '1s']
        if main:
            args += ['--protocol-version', '1.1', '--repetition', '1', '--planned-order', '3' if profile == 'steady' else '6', '--actual-order', '1']
        with patch.object(run_pilot, 'run_load', delayed_load), \
             patch.object(run_pilot, 'Observer', Observer), patch.object(run_pilot, 'versions', fixture.fake_versions), \
             patch.object(autoscaling, 'Logs', Logs), patch.object(Path, 'read_text', read), \
             patch.object(run_pilot.shutil, 'copyfile', copy), \
             patch.object(run_pilot.shutil, 'which', return_value=shutil.which('k6') or 'test-k6'), \
             patch('main_protocol.recover', return_value={'test_stub': True}), \
             patch('main_protocol.runtime_context', return_value={'test_stub': True}), \
             patch('main_protocol.check_configuration') as configuration, \
             patch('main_protocol.settle', return_value={'test_stub': True}) as settle:
            if interrupt:
                with patch.object(run_pilot, 'run_load', side_effect=KeyboardInterrupt):
                    code = run_pilot.main(args)
            else:
                code = run_pilot.main(args)
        if main and not interrupt and not fail_warmup:
            self.assertEqual(settle.call_count, 2)
            self.assertFalse(settle.call_args_list[0].args[2:] or ())
            self.assertEqual(settle.call_args_list[1].args[2:], (True,))
        return fixture.folder, code

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
    def test_real_k6_burst_dynamic_collection_analysis_and_recovery(self):
        folder, code = self.exercise()
        check = json.loads((folder / 'collection-check.json').read_text())
        self.assertEqual(code, 0, check)
        self.assertTrue(check['valid'], check)
        self.assertEqual(len(check['logs']['pods']), 2)
        metadata = json.loads((folder / 'metadata.json').read_text())
        self.assertEqual(metadata['profile'], 'burst')
        self.assertAlmostEqual(metadata['duration_seconds'], 1)
        self.assertTrue(metadata['recovery']['successful'])
        output = folder / 'analysis'
        self.assertEqual(analyze.main([str(folder), '--output-dir', str(output), '--no-plots']), 0)
        scaling = json.loads((output / 'scaling.json').read_text())[folder.name]
        self.assertTrue(scaling['growth_observed'])
        self.assertTrue(scaling['reduction_observed'])
        self.assertEqual(sum(s['completed'] for s in scaling['stages']), check['counts']['completed'])
        self.assertFalse(any(t.name == 'pilot-observer' for t in run_pilot.threading.enumerate()))

    @unittest.skipUnless(shutil.which('k6'), 'k6 is required for this integration check')
    def test_slow_k6_start_keeps_scaling_inside_the_observed_load_window(self):
        folder, code = self.exercise(startup_delay=1)
        data = analyze.load_results(folder)
        self.assertEqual(code, 0, data['check'])
        self.assertTrue(data['check']['valid'], data['check'])
        detail = analyze.scaling_details(data)
        before = [p for p in detail['timeline'] if p['seconds'] < 0 and p['desired'] is not None]
        self.assertTrue(before)
        self.assertTrue(all(p['running'] == p['desired'] == 1 for p in before))
        self.assertTrue(detail['growth_observed'])
        self.assertTrue(detail['reduction_observed'])

    def test_interrupt_saves_partial_records_stops_observer_and_restores(self):
        folder, code = self.exercise(interrupt=True)
        self.assertEqual(code, 130)
        metadata = json.loads((folder / 'metadata.json').read_text())
        self.assertFalse(metadata['collection_valid'])
        self.assertTrue(metadata['recovery']['successful'])
        self.assertTrue((folder / 'log-coverage.json').exists())
        self.assertTrue((folder / 'cluster-after.json').exists())
        self.assertFalse(any(t.name == 'pilot-observer' for t in run_pilot.threading.enumerate()))

    def test_bad_warmup_never_enables_hpa_or_starts_load_and_restores(self):
        with patch.object(autoscaling.Session, 'enable') as enable, patch.object(run_pilot, 'run_load') as load:
            folder, code = self.exercise(fail_warmup=True)
            enable.assert_not_called()
            load.assert_not_called()
        self.assertEqual(code, 1)
        self.assertTrue(json.loads((folder / 'recovery.json').read_text())['successful'])


if __name__ == '__main__':
    unittest.main()

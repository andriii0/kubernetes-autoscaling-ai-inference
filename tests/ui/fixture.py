"""Temporary local UI server; never starts a benchmark or scans real processes."""

import io
import json
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lab.results import Results
from lab.server import Server


def write(folder, name, value):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(value), encoding='utf-8')


def seed(root):
    for order in range(1, 19):
        run = root / 'results/main/example' / f'attempt-{order:02d}-fixed-1-burst'
        write(run, 'metadata.json', dict(
            mode='fixed-1', profile='burst', protocol_version='1.1', rate=8, low_rate=2,
            started_at_utc='2026-10-25T12:00:00Z', finished_at_utc='2026-10-25T12:20:00Z',
            exit_code=99 if order == 1 else 0, collector_exit_code=0, collection_valid=True,
            workload={'main_protocol': {'primary_p95_ms': 5000}}))
        write(run, 'collection-check.json', dict(
            valid=True, counts=dict(successful=20, failed=0, completed=20, unfinished=0, dropped=0)))
        write(run, 'assessment.json', dict(
            data_valid=True, overall='fail' if order == 1 else 'pass',
            primary={'name': 'peak', 'p95_ms': 6000 if order == 1 else 1000}))
    write(root / 'results/pilot/broken', 'metadata.json',
          dict(exit_code=1, collection_valid=False, mode='fixed-1', profile='steady'))
    write(root / 'results/pilot/broken', 'collection-check.json', dict(valid=False))
    custom = root / 'results/custom-metric/comparison-example'
    write(custom, 'manifest.json', dict(protocol='active-requests-comparison-v2', cells=[{}] * 6,
                                       completed=[], status='stopped'))
    write(custom / 'attempt-01-cpu', 'metadata.json',
          dict(exit_code=1, collection_valid=False, mode='autoscaling', profile='burst', rate=12))
    (custom.parent / 'notes.md').write_text('Active client requests at Envoy show work building up.',
                                          encoding='utf-8')
    (custom / 'attempt-01-cpu/notes.md').write_text('Stopped because the clock check failed.', encoding='utf-8')

    custom = root / 'results/custom-metric/comparison-complete'
    completed = []
    for order, (policy, on_time, errors, p95) in enumerate([
            ('cpu', 37, 86, 28912), ('active-1', 296, 0, 6978),
            ('active-1', 345, 0, 4820), ('cpu', 95, 59, 28355),
            ('cpu', 41, 49, 28322), ('active-1', 262, 0, 11361)], 1):
        name = f'attempt-{order:02d}-{policy}' + ('-retry-01' if order == 5 else '')
        write(custom / name, 'metadata.json', dict(
            mode='autoscaling', custom_metric_policy=policy, profile='burst', protocol_version='1.1',
            started_at_utc='2026-11-14T20:00:00Z', finished_at_utc='2026-11-14T20:20:00Z',
            exit_code=0 if order == 3 else 99, collection_valid=True))
        write(custom / name, 'collection-check.json', dict(valid=True))
        completed.append(dict(run=name, policy=policy, order=order,
                              assessment=dict(data_valid=True, overall='pass' if order == 3 else 'fail',
                                              primary=dict(name='peak', failed=errors, p95_ms=p95)),
                              outcomes=dict(peak_started=360, peak_on_time_successes=on_time)))
    write(custom, 'manifest.json', dict(protocol='active-requests-comparison-v3', status='finished',
                                       cells=[{}] * 6, completed=completed))
    write(custom / 'attempt-05-cpu', 'metadata.json', dict(
        mode='autoscaling', custom_metric_policy='cpu', exit_code=1, collection_valid=False))
    pending = root / 'results/custom-metric/preparation-pending/target-2'
    write(pending, 'metadata.json', dict(mode='autoscaling', custom_metric_policy='active-2',
                                        status='running', collection_valid=False, finished_at_utc=None,
                                        collector_exit_code=None, exit_code=None))
    stopped = root / 'results/custom-metric/series-stopped'
    write(stopped / 'preparation-new/target-1', 'metadata.json', dict(mode='autoscaling'))
    (stopped / 'notes.md').write_text('Historical cycle: target 2 stopped on a clock difference. <script>literal</script>', encoding='utf-8')


def fake_process(command, **_kwargs):
    # Backend command construction is real; there is no child interpreter or k6.
    if '--dry-run' not in command:
        raise AssertionError('Browser fixture must never request a live launch')
    return Mock(stdout=io.StringIO('Dry run passed\n'), wait=Mock(return_value=0))


def main():
    with tempfile.TemporaryDirectory(prefix='inference-ui-') as temporary:
        root = Path(temporary)
        seed(root)
        with patch('lab.jobs.ROOT', root), patch('lab.jobs.external_runs', return_value=[]), \
                patch('lab.jobs.subprocess.Popen', side_effect=fake_process):
            server = Server(('127.0.0.1', 0), Results(root / 'results'), dry_only=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                print(json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', root=str(root))), flush=True)
                sys.stdin.read()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    main()

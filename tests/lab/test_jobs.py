import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lab.jobs import Jobs
from lab.launch import main as pilot_main
from lab.results import Results
from lab.server import Handler, Server


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.results = Results(Path(self.temp.name) / 'results')
        self.results.root.mkdir()

    def test_dry_pilot_validates_without_service_or_results(self):
        with patch('lab.launch.ROOT', Path(__file__).resolve().parents[2]), patch('sys.stdout', new_callable=io.StringIO) as output:
            # The adapter imports these only inside main; no runtime method is called in dry run.
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bench'))
            self.addCleanup(sys.path.pop, 0)
            with patch('runtime.service_url', side_effect=AssertionError('Dry run opened tunnel')):
                self.assertEqual(pilot_main(['--dry-run', '--activity-note', 'test']), 0)
        self.assertIn('arguments valid', output.getvalue())
        self.assertIn('--rate 2', output.getvalue())

    def test_active_and_external_launch_exclusion(self):
        jobs = Jobs(self.results)
        jobs.current = {'active': True}
        with self.assertRaisesRegex(ValueError, 'already active'):
            jobs.start('pilot', True, '', 'test')
        jobs.current = None
        with patch('lab.jobs.external_runs', return_value=[{'ProcessId': 123}]), patch('lab.jobs.subprocess.Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'Another experiment'):
                jobs.start('pilot', False, '', 'test')
            popen.assert_not_called()

    def test_process_check_failure_and_dry_only_block_live(self):
        with patch('lab.jobs.external_runs', side_effect=OSError('Cannot scan')):
            with self.assertRaisesRegex(ValueError, 'Cannot check'):
                Jobs(self.results).start('pilot', False, '', 'test')
        with self.assertRaisesRegex(ValueError, 'dry-run mode'):
            Jobs(self.results, dry_only=True).start('pilot', False, '', 'test')

    def test_series_cannot_initialize_new_directory(self):
        with self.assertRaisesRegex(ValueError, 'existing main series'):
            Jobs(self.results).start('series', True, 'main/new', 'test')
        self.assertFalse((self.results.root / 'main/new').exists())

    def test_dry_job_builds_command_and_saves_only_ui_log(self):
        jobs = Jobs(self.results)
        with patch('lab.jobs.ROOT', Path(self.temp.name)), patch('lab.jobs.subprocess.Popen') as popen:
            popen.return_value.stdout = io.StringIO('Dry run passed\n')
            popen.return_value.wait.return_value = 0
            with patch('lab.jobs.threading.Thread') as thread:
                launched = jobs.start('pilot', True, '', 'test')
                args = thread.call_args.kwargs['args']
            jobs._watch(*args)
        self.assertIn('--dry-run', launched['command'])
        self.assertEqual(jobs.current['phase'], 'Dry run passed')
        self.assertFalse(jobs.current['active'])
        self.assertTrue(Path(launched['log']).is_file())
        self.assertEqual(list(self.results.root.iterdir()), [])


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.server = Server(('127.0.0.1', 0), Results(self.temp.name), dry_only=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_static_catalog_and_path_boundary(self):
        with urlopen(self.url) as response:
            self.assertIn(b'Inference Lab', response.read())
        with urlopen(self.url + '/api/results') as response:
            self.assertEqual(json.load(response), [])
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + '/plot?id=../private.png')
        self.assertEqual(error.exception.code, 400)

    def test_mutations_require_token_and_local_origin(self):
        for headers in ({}, {'X-Lab-Token': self.server.token, 'Origin': 'https://other.example'}):
            request = Request(self.url + '/api/launch', data=b'{}', headers=headers)
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 403)
        request = Request(self.url + '/api/launch', data=json.dumps({'kind':'pilot','dry_run':False,'activity':'none'}).encode(),
                          headers={'X-Lab-Token':self.server.token})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertIn(b'dry-run mode', error.exception.read())

    def test_closed_browser_connection_is_not_retried(self):
        handler = object.__new__(Handler)
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock(side_effect=ConnectionResetError('Browser closed'))
        handler.wfile = Mock()
        handler.send({'saved': True})
        self.assertTrue(handler.close_connection)
        handler.send_response.assert_called_once_with(200)
        handler.wfile.write.assert_not_called()

    def test_open_folder_uses_selected_directory(self):
        folder = Path(self.temp.name) / 'pilot/example'
        folder.mkdir(parents=True)
        request = Request(self.url + '/api/open', data=b'{"id":"pilot/example"}',
                          headers={'X-Lab-Token': self.server.token})
        with patch('lab.server.os.startfile', create=True) as open_folder:
            with urlopen(request) as response:
                self.assertTrue(json.load(response)['opened'])
            open_folder.assert_called_once_with(str(folder))

    def test_invalid_pilot_payload_has_no_launch_side_effects(self):
        request = Request(self.url + '/api/launch', data=json.dumps({
            'kind': 'pilot', 'dry_run': True, 'activity': 'test', 'pilot': {'rate': -1}
        }).encode(), headers={'X-Lab-Token': self.server.token})
        with patch('lab.jobs.subprocess.Popen') as process, self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 400)
        process.assert_not_called()
        self.assertIsNone(self.server.jobs.current)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])


if __name__ == '__main__':
    unittest.main()

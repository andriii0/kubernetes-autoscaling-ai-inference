import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import run_lock


class RunLockTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "run.lock"
        p = patch.object(run_lock, "LOCK_PATH", self.path)
        p.start()
        self.addCleanup(p.stop)
        self.environment = dict(os.environ)
        self.environment.pop(run_lock.TOKEN_ENV, None)
        self.environment["PYTHONPATH"] = str(Path(run_lock.__file__).parent)

    def command(self, body):
        return [sys.executable, "-B", "-c", "from pathlib import Path; import run_lock; "
                + f"run_lock.LOCK_PATH=Path({str(self.path)!r}); " + body]

    def test_independent_process_rejected_and_exception_releases(self):
        with self.assertRaisesRegex(RuntimeError, "fixture"):
            with run_lock.experiment_lock():
                result = subprocess.run(self.command("exec('with run_lock.experiment_lock(): print(123)')"),
                    env=self.environment, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("cluster is locked", result.stderr)
                raise RuntimeError("fixture")
        result = subprocess.run(self.command("exec('with run_lock.experiment_lock(): print(123)')"),
                                env=self.environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_registered_child_keeps_exclusion_after_parent_scope_exits(self):
        child = None
        try:
            with run_lock.experiment_lock():
                environment = dict(self.environment)
                environment[run_lock.TOKEN_ENV] = os.environ[run_lock.TOKEN_ENV]
                body = "import sys\nwith run_lock.experiment_lock():\n print(123,flush=True)\n sys.stdin.readline()"
                child = subprocess.Popen(self.command(body), env=environment, stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                line = child.stdout.readline().strip()
                self.assertEqual(line, '123', child.stderr.read() if not line else '')
            blocked = subprocess.run(self.command("exec('with run_lock.experiment_lock(): print(456)')"),
                                     env=self.environment, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("cluster is locked", blocked.stderr)
        finally:
            if child:
                child.communicate('done\n' if child.poll() is None else None, timeout=10)
        with run_lock.experiment_lock():
            self.assertIn(os.getpid(), run_lock.participant_pids())

    def test_registered_load_survives_owner_and_finished_handle_is_not_alive(self):
        child = subprocess.Popen([sys.executable, '-B', '-c', 'import sys; sys.stdin.readline()'],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            with run_lock.experiment_lock():
                run_lock.register_process(child)
            with self.assertRaisesRegex(ValueError, 'cluster is locked'):
                with run_lock.experiment_lock():
                    pass
            child.terminate()
            child.wait(timeout=10)
            self.assertIsNone(run_lock.process_identity(child.pid))
            with run_lock.experiment_lock():
                pass
        finally:
            if child.poll() is None:
                child.terminate()
            child.communicate(timeout=10)

    def test_stale_process_identity_does_not_block_new_experiment(self):
        self.path.write_bytes(b' ' + json.dumps({'token': 'old', 'participants':
                              {str(os.getpid()): 'previous-process-with-same-pid'}}).encode())
        with run_lock.experiment_lock():
            self.assertNotEqual(os.environ[run_lock.TOKEN_ENV], 'old')

    def test_own_venv_redirector_is_ignored_but_an_independent_driver_is_not(self):
        from runtime import foreign_processes
        binary = str(Path("venv/python.exe").resolve())
        processes = [dict(ProcessId=10, ExecutablePath=binary),
                     dict(ProcessId=11, ParentProcessId=10, ExecutablePath="base/python.exe"),
                     dict(ProcessId=20, ExecutablePath=binary),
                     dict(ProcessId=21, ParentProcessId=20, ExecutablePath="base/python.exe")]
        self.assertEqual([p["ProcessId"] for p in foreign_processes(processes, [11], binary)], [20, 21])
        processes[0]["ExecutablePath"] = "unrelated/python.exe"
        self.assertEqual([p["ProcessId"] for p in foreign_processes(processes, [11], binary)], [10, 20, 21])

    def test_dry_run_does_not_create_registry(self):
        @run_lock.exclusive_main
        def dry(argv):
            return 42
        self.assertEqual(dry(['--dry-run']), 42)
        self.assertFalse(self.path.exists())


    def test_atomic_save_failures_preserve_owner_and_block_workload(self):
        with run_lock.experiment_lock():
            state_path = self.path.with_suffix(".lock.json")
            committed = state_path.read_bytes()
            for operation in ("replace", "fsync"):
                with self.subTest(operation=operation):
                    with patch.object(run_lock.os, operation, side_effect=OSError("interrupted write")):
                        with self.assertRaisesRegex(OSError, "interrupted write"):
                            with run_lock._registry() as state:
                                state["participants"]["999"] = "new-child"
                    self.assertEqual(state_path.read_bytes(), committed)
                    self.assertIn(os.getpid(), run_lock.participant_pids())
            with patch.object(run_lock.json, "dumps", side_effect=ValueError("bad value")):
                with self.assertRaisesRegex(ValueError, "bad value"):
                    with run_lock._registry() as state:
                        state["token"] = "replacement"
            self.assertEqual(state_path.read_bytes(), committed)
        # Failed ownership persistence must stop before entering the workload.
        entered = False
        with patch.object(run_lock.os, "replace", side_effect=OSError("interrupted write")):
            with self.assertRaises(OSError):
                with run_lock.experiment_lock():
                    entered = True
        self.assertFalse(entered)

    def test_live_legacy_owner_blocks_migration_without_changes(self):
        legacy = b' ' + json.dumps({'token': 'old', 'participants':
                   {str(os.getpid()): run_lock.process_identity(os.getpid())}}).encode()
        self.path.write_bytes(legacy)
        with self.assertRaisesRegex(ValueError, 'legacy registry'):
            with run_lock.experiment_lock():
                self.fail("must not start")
        self.assertEqual(self.path.read_bytes(), legacy)
        self.assertFalse(self.path.with_suffix('.lock.json').exists())

    def test_corrupt_legacy_registry_is_preserved_and_explained(self):
        for payload in (b' {"token":', b' []', b' {"participants": {}}', b' \xff'):
            with self.subTest(payload=payload):
                self.path.write_bytes(payload)
                with self.assertRaisesRegex(ValueError, 'registry is corrupt.*no load started'):
                    with run_lock.experiment_lock():
                        self.fail("must not start")
                self.assertEqual(self.path.read_bytes(), payload)

    def test_migration_blocks_old_reader_and_ignores_abandoned_temp(self):
        self.path.write_bytes(b' {}')
        with run_lock.experiment_lock():
            with self.assertRaises(json.JSONDecodeError):
                json.loads(self.path.read_bytes()[1:])
            self.path.with_suffix('.lock.json.abandoned.tmp').write_bytes(b'{')
            self.assertIn(os.getpid(), run_lock.participant_pids())

    def test_missing_or_corrupt_committed_state_fails_closed(self):
        with run_lock.experiment_lock():
            pass
        state_path = self.path.with_suffix('.lock.json')
        state_path.unlink()
        with self.assertRaisesRegex(ValueError, 'registry state is missing'):
            with run_lock.experiment_lock():
                self.fail("must not start")
        state_path.write_bytes(b'{"token":')
        with self.assertRaisesRegex(ValueError, 'registry is corrupt'):
            with run_lock.experiment_lock():
                self.fail("must not start")
        self.assertEqual(state_path.read_bytes(), b'{"token":')

    def test_interrupted_migration_cannot_start_workload(self):
        self.path.write_bytes(b' {}')
        real_fsync = run_lock.os.fsync
        calls = 0
        def fail_marker(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("marker not durable")
            return real_fsync(fd)
        with patch.object(run_lock.os, 'fsync', side_effect=fail_marker):
            with self.assertRaisesRegex(OSError, 'marker not durable'):
                with run_lock.experiment_lock():
                    self.fail("must not start")
        with run_lock.experiment_lock():
            self.assertIn(os.getpid(), run_lock.participant_pids())

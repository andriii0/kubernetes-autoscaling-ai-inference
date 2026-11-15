"""One live experiment per local cluster, including registered child launchers."""

from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import uuid

TOKEN_ENV = "INFERENCE_LAB_RUN_TOKEN"
LOCK_PATH = Path(tempfile.gettempdir()) / "inference-lab-ai-lab.lock"
_local = threading.local()


def process_identity(pid):
    """Distinguish a living process from a later reuse of its PID."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:
                return None
            raise OSError(error, "Cannot verify experiment process")
        try:
            stamps = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in stamps)):
                raise ctypes.WinError(ctypes.get_last_error())
            if stamps[1].dwHighDateTime or stamps[1].dwLowDateTime:
                return None
            return str((stamps[0].dwHighDateTime << 32) | stamps[0].dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except FileNotFoundError:
        return None


@contextmanager
def _registry():
    # Lock the first byte; the JSON begins at byte 1. Keep this section short.
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "r+b", buffering=0) as handle:
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b" ")
        deadline = time.monotonic() + 5
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ValueError("Experiment registry is busy; no load started")
                time.sleep(.05)
        try:
            handle.seek(1)
            raw = handle.read()
            state = json.loads(raw) if raw else {}
            yield state
            handle.seek(1)
            handle.write(json.dumps(state).encode())
            handle.truncate()
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _living(state):
    return {pid: stamp for pid, stamp in state.get("participants", {}).items()
            if process_identity(int(pid)) == stamp}


def participant_pids():
    """Only the current experiment's registered launchers may be ignored by scans."""
    token = os.environ.get(TOKEN_ENV)
    if not token:
        return []
    with _registry() as state:
        return [int(pid) for pid in _living(state)] if state.get("token") == token else []


@contextmanager
def experiment_lock():
    if getattr(_local, "active", False):
        yield
        return
    pid, identity = str(os.getpid()), process_identity(os.getpid())
    previous = os.environ.get(TOKEN_ENV)
    with _registry() as state:
        living = _living(state)
        if living and (not previous or previous != state.get("token")):
            raise ValueError("Another experiment is running; cluster is locked")
        token = state["token"] if living else uuid.uuid4().hex
        state.update(token=token, participants={**living, pid: identity})
    os.environ[TOKEN_ENV] = token
    _local.active = True
    try:
        yield
    finally:
        _local.active = False
        try:
            with _registry() as state:
                if state.get("token") == token:
                    state.get("participants", {}).pop(pid, None)
        finally:
            if previous is None:
                os.environ.pop(TOKEN_ENV, None)
            else:
                os.environ[TOKEN_ENV] = previous


def register_process(process):
    """Keep k6 visible to the lock even if its Python launcher disappears."""
    token = os.environ.get(TOKEN_ENV)
    if not token or type(process.pid) is not int:
        return
    identity = process_identity(process.pid)
    if identity is None:
        return
    with _registry() as state:
        if state.get("token") != token:
            raise ValueError("experiment ownership changed before child registration")
        state.setdefault("participants", {})[str(process.pid)] = identity


def exclusive_main(function):
    """Keep dry checks read-only; hold live ownership before runtime preparation."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        argv = args[0] if args else kwargs.get("argv")
        argv = sys.argv[1:] if argv is None else argv
        dry = "--dry-run" in argv or (function.__module__ in
              ("run_custom_comparison", "run_custom_series", "prepare_custom_metric") and "--execute" not in argv)
        # Standalone Python scripts run as __main__.
        if Path(function.__code__.co_filename).stem in ("run_custom_comparison", "run_custom_series", "prepare_custom_metric"):
            dry = "--execute" not in argv
        if dry:
            return function(*args, **kwargs)
        with experiment_lock():
            return function(*args, **kwargs)
    return wrapped

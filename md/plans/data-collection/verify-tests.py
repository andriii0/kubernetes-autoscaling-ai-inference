"""Prove selected negative tests detect disabled validators in temporary copies."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parents[3]
mutations = (
    ("unfinished", "if unfinished:", "test_unfinished_request_is_visible"),
    ("order", "if times and observed <= times[-1]:", "test_observation_order_gaps_and_coverage_have_distinct_failures"),
    ("gap", 'if times and observed - times[-1] > 2 * metadata["observer_interval_seconds"]:',
     "test_observation_order_gaps_and_coverage_have_distinct_failures"),
)
with tempfile.TemporaryDirectory() as temporary:
    folder = Path(temporary)
    for name in ("pilot_records.py", "test_pilot_records.py"):
        shutil.copyfile(root / "bench" / name, folder / name)
    original = (folder / "pilot_records.py").read_text(encoding="utf-8")
    baseline = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_pilot_records"],
                              cwd=folder, capture_output=True, text=True)
    if baseline.returncode:
        raise AssertionError("baseline tests failed:\n" + baseline.stdout + baseline.stderr)
    for name, condition, method in mutations:
        assert original.count(condition) == 1, condition
        (folder / "pilot_records.py").write_text(original.replace(condition, "if False:"), encoding="utf-8")
        target = f"test_pilot_records.RecordTests.{method}"
        result = subprocess.run([sys.executable, "-B", "-m", "unittest", target],
                                cwd=folder, capture_output=True, text=True)
        output = result.stdout + result.stderr
        if result.returncode == 0 or f"FAIL: {method}" not in output or "ERROR:" in output:
            raise AssertionError(f"disabled {name} check was not caught by its assertion:\n{output}")
        print(f"caught disabled {name} check")
print("negative-test verification passed")

"""Make the standalone bench modules importable during unittest discovery."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))

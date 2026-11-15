"""Build the pinned local k6 runtime with the project's monotonic timer."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".bench-runtime"
MODULE = ROOT / "bench/monotonic"
K6_VERSION = "v2.2.0"
XK6_VERSION = "v1.5.1"
GO_VERSION = "go1.26.5"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    return {p.name: digest(p) for p in sorted(MODULE.iterdir()) if p.suffix in (".go", ".mod", ".sum")}


def runtime():
    binary = RUNTIME / ("k6.exe" if os.name == "nt" else "k6")
    try:
        record = json.loads((RUNTIME / "runtime.json").read_text(encoding="utf-8"))
        if record["binary_sha256"] != digest(binary) or record["sources"] != source_hashes():
            raise ValueError("local k6 runtime or timer source changed; rebuild it")
        if record["k6_version"] != K6_VERSION or record["xk6_version"] != XK6_VERSION or record["go_version"] != GO_VERSION:
            raise ValueError("local k6 runtime version changed; rebuild it")
        return str(binary), record
    except (OSError, KeyError) as error:
        raise ValueError("Build the monotonic k6 runtime first: python bench/build_k6.py") from error


def main():
    RUNTIME.mkdir(exist_ok=True)
    environment = dict(os.environ, GOTOOLCHAIN=GO_VERSION, GOWORK="off")
    subprocess.run(["go", "mod", "tidy"], cwd=MODULE, env=environment, check=True)
    binary = RUNTIME / ("k6.exe" if os.name == "nt" else "k6")
    subprocess.run(["go", "run", f"go.k6.io/xk6/cmd/xk6@{XK6_VERSION}", "build", K6_VERSION,
                    "--with", f"example.com/inference-lab/monotonic={MODULE}", "--output", str(binary)],
                   cwd=RUNTIME, env=environment, check=True)
    version = subprocess.run([str(binary), "version"], check=True, capture_output=True, text=True).stdout
    if "example.com/inference-lab/monotonic" not in version:
        raise ValueError("built runtime does not report the monotonic extension")
    record = dict(k6_version=K6_VERSION, xk6_version=XK6_VERSION, go_version=GO_VERSION,
                  binary_sha256=digest(binary), sources=source_hashes(), version_output=version)
    (RUNTIME / "runtime.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())

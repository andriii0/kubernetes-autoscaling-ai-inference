"""Recheck preserved evidence and current documentation without changing saved runs."""
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(__file__).resolve().parents[3]
baseline = json.loads(Path(__file__).with_name("raw-evidence-sha256.json").read_text())
for name, expected in baseline.items():
    actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
    assert actual == expected, f"Historical evidence changed: {name}"

series = root / "results/observer-overhead-2026-10-16-series1"
spec = importlib.util.spec_from_file_location("overhead_integrity", series / "analyze-overhead.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
saved = json.loads((series / "analysis.json").read_text())
with tempfile.TemporaryDirectory() as temporary:
    copied = Path(temporary) / "project/results/series"
    shutil.copytree(series, copied, ignore=shutil.ignore_patterns("__pycache__"))
    actual = module.analyze(copied)
    assert actual == saved, "Reanalysis differs from the saved overhead report"

def anchors(path):
    content = path.read_text(encoding="utf-8")
    found = set(re.findall(r'<a\s+(?:id|name)=[\"\']([^\"\']+)', content))
    for heading in re.findall(r"^#{1,6}\s+(.+)$", content, re.MULTILINE):
        heading = re.sub(r"[`*_]", "", heading).lower()
        found.add(re.sub(r"[^\w\- ]", "", heading).replace(" ", "-"))
    return found

count = 0
files = [root / "README.md", root / "AGENTS.md", *(root / "md").rglob("*.md"), root / "docs/README.md"]
for file in files:
    text = file.read_text(encoding="utf-8")
    for raw in re.findall(r"\[[^\]]*\]\((<[^>]+>|[^\s)]+)\)", text):
        raw = raw[1:-1] if raw.startswith("<") else raw
        url = urlsplit(raw)
        if url.scheme or url.netloc:
            continue
        destination = (file.parent / unquote(url.path)).resolve() if url.path else file
        assert destination.exists(), (file, raw, "missing link target")
        if url.fragment and destination.suffix == ".md":
            assert unquote(url.fragment) in anchors(destination), (file, raw, "missing anchor")
        count += 1

print(f"Preserved {len(baseline)} historical evidence files; real-series aggregates match; {count} local links resolve.")
print("measurement integrity verification passed")

"""Check local Markdown links without accessing the network."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


LINK = re.compile(r"(?<!!)\[[^\]]+\]\((<[^>]+>|[^)\s]+)")
ROOT = Path(__file__).resolve().parent.parent


def markdown_files() -> list[Path]:
    files = {ROOT / "README.md"}
    for directory in (ROOT / "md", ROOT / "docs", ROOT / "results"):
        if directory.exists():
            files.update(directory.rglob("*.md"))
    return sorted(path for path in files if path.is_file())


def check() -> list[str]:
    errors = []
    checked = 0
    for source in markdown_files():
        in_code = False
        prose = []
        for line in source.read_text(encoding="utf-8").splitlines():
            if line.startswith("```"):
                in_code = not in_code
                continue
            if not in_code:
                prose.append(line)
        for match in LINK.finditer("\n".join(prose)):
            target = match.group(1).strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            checked += 1
            path = (source.parent / unquote(target)).resolve()
            if not path.exists():
                errors.append(f"{source.relative_to(ROOT)}: {target}")
    print(f"Checked {checked} local Markdown links in {len(markdown_files())} files")
    return errors


if __name__ == "__main__":
    failures = check()
    if failures:
        print("Broken local links:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        raise SystemExit(1)

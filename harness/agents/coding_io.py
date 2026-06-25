"""Shared file I/O helpers for coding-agent adapters."""

from __future__ import annotations

import re
from pathlib import Path

FILE_BLOCK = re.compile(r'<file path="(?P<path>[^"]+)">\n?(?P<body>.*?)</file>', re.DOTALL)


def read_sources(workdir: Path) -> dict[str, str]:
    """Read editable Python sources from a task workspace.

    Tests and harness/private helper files are intentionally excluded so the
    agent sees the same small project surface that will be patched.
    """
    sources: dict[str, str] = {}
    for p in sorted(workdir.rglob("*.py")):
        rel = p.relative_to(workdir)
        if rel.parts[0] in {"tests"} or any(part.startswith("_") for part in rel.parts):
            continue
        sources[str(rel).replace("\\", "/")] = p.read_text(encoding="utf-8")
    return sources


def files_blob(workdir: Path) -> str:
    sources = read_sources(workdir)
    return "\n\n".join(f'<file path="{path}">\n{body}</file>' for path, body in sources.items())


def apply_file_blocks(workdir: Path, text: str) -> int:
    """Apply safe ``<file path="...">`` blocks and return the write count."""
    changed = 0
    for match in FILE_BLOCK.finditer(text):
        rel = Path(match.group("path"))
        if rel.is_absolute() or ".." in rel.parts:
            continue
        dst = workdir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(match.group("body"), encoding="utf-8")
        changed += 1
    return changed

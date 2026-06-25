"""Shared file I/O helpers for coding-agent adapters."""

from __future__ import annotations

import re
from pathlib import Path

FILE_BLOCK = re.compile(r'<file path="(?P<path>[^"]+)">\n?(?P<body>.*?)</file>', re.DOTALL)
PYTHON_FENCE = re.compile(r"```(?:python|py)?\s*\n(?P<body>.*?)```", re.DOTALL | re.IGNORECASE)


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


def apply_agent_response(workdir: Path, text: str) -> int:
    """Apply an agent response to the workspace.

    The preferred contract is explicit ``<file path="...">`` blocks.  Some
    models still return a single fenced Python block even after being told not
    to.  If the task workspace has exactly one editable source file, that
    fallback is safe and useful: the target path is unambiguous and we can avoid
    counting a correct patch as a formatting-only failure.
    """
    changed = apply_file_blocks(workdir, text)
    if changed:
        return changed

    matches = PYTHON_FENCE.findall(text)
    sources = read_sources(workdir)
    if len(matches) != 1 or len(sources) != 1:
        return 0

    rel_path = next(iter(sources))
    body = matches[0].strip()
    if not body:
        return 0
    dst = workdir / rel_path
    dst.write_text(body + "\n", encoding="utf-8")
    return 1

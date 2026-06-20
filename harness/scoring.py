"""테스트 실행 및 수정 규모 측정."""

from __future__ import annotations

import difflib
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

IGNORED_TOP_LEVEL = {"tests", "_solution"}


def run_pytest(workdir: Path) -> tuple[int, int, str]:
    """workdir에서 pytest를 돌리고 (passed, total, log)를 반환한다.

    junit-xml로 결과를 파싱해 통과/전체 개수를 정확히 세고,
    stdout+stderr는 합쳐서 로그 텍스트로 그대로 보존한다(아티팩트 저장용).
    """
    report = workdir / "_junit.xml"
    full_env = {**os.environ, "PYTHONPATH": str(workdir), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests",
             "--junitxml", str(report), "-q", "-p", "no:cacheprovider"],
            cwd=workdir, env=full_env,
            capture_output=True, text=True,
            timeout=300,
        )
        log = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        log = f"pytest timeout: {exc}"

    if not report.exists():
        return 0, 0, log
    root = ET.parse(report).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        return 0, 0, log
    total = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    passed = total - failures - errors - skipped
    return passed, total, log


@dataclass
class DiffResult:
    """수정 전/후 디렉터리 비교 결과."""

    files_changed: int
    lines_changed: int
    text: str


def _diffable_files(before: Path, after: Path) -> list[Path]:
    after_files = {p.relative_to(after) for p in after.rglob("*") if p.is_file()}
    before_files = {p.relative_to(before) for p in before.rglob("*") if p.is_file()}
    rels = []
    for rel in after_files | before_files:
        if rel.parts and rel.parts[0] in IGNORED_TOP_LEVEL:
            continue
        if rel.name.startswith("_"):
            continue
        rels.append(rel)
    return sorted(rels, key=str)


def compute_diff(before: Path, after: Path) -> DiffResult:
    """두 디렉터리 트리를 비교해 변경 파일 수, 변경 라인 수, unified diff 텍스트를 반환한다."""
    files_changed = 0
    lines_changed = 0
    chunks: list[str] = []

    for rel in _diffable_files(before, after):
        b_path, a_path = before / rel, after / rel
        b = b_path.read_text(encoding="utf-8").splitlines(keepends=True) if b_path.exists() else []
        a = a_path.read_text(encoding="utf-8").splitlines(keepends=True) if a_path.exists() else []
        if b == a:
            continue
        diff_lines = list(difflib.unified_diff(b, a, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
        if not diff_lines:
            continue
        files_changed += 1
        lines_changed += sum(
            1 for line in diff_lines
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        )
        chunks.append("".join(diff_lines))

    return DiffResult(files_changed, lines_changed, "\n".join(chunks))

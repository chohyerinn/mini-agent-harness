"""테스트 실행 및 수정 규모 측정."""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def run_pytest(workdir: Path) -> tuple[int, int]:
    """workdir에서 pytest를 돌리고 (passed, total)을 반환한다.

    junit-xml로 결과를 파싱해 통과/전체 개수를 정확히 센다.
    """
    report = workdir / "_junit.xml"
    env = {"PYTHONPATH": str(workdir), "PYTHONDONTWRITEBYTECODE": "1"}
    import os

    full_env = {**os.environ, **env}
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests",
         "--junitxml", str(report), "-q", "-p", "no:cacheprovider"],
        cwd=workdir, env=full_env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=300,
    )
    if not report.exists():
        return 0, 0
    root = ET.parse(report).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        return 0, 0
    total = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    passed = total - failures - errors - skipped
    return passed, total


def diff_size(before: Path, after: Path) -> tuple[int, int]:
    """두 디렉터리 트리를 비교해 (변경 파일 수, 변경 라인 수)를 반환한다."""
    import difflib

    files_changed = 0
    lines_changed = 0
    after_files = {p.relative_to(after) for p in after.rglob("*") if p.is_file()}
    before_files = {p.relative_to(before) for p in before.rglob("*") if p.is_file()}

    for rel in after_files | before_files:
        if rel.parts and rel.parts[0] in {"tests", "_solution"} or rel.name.startswith("_"):
            continue
        b = (before / rel).read_text(encoding="utf-8").splitlines() if rel in before_files else []
        a = (after / rel).read_text(encoding="utf-8").splitlines() if rel in after_files else []
        delta = sum(1 for line in difflib.ndiff(b, a) if line[0] in "+-")
        if delta:
            files_changed += 1
            lines_changed += delta
    return files_changed, lines_changed

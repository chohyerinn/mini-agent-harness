"""단일 과제 실행기: 격리된 작업 폴더에서 에이전트를 돌리고 채점한다."""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from .agents.base import Agent
from .models import RunResult, Task
from .scoring import diff_size, run_pytest


def run_task(task: Task, agent: Agent) -> RunResult:
    """task를 임시 폴더에 복제 → 에이전트 실행 → 테스트/수정량 채점."""
    tmp = Path(tempfile.mkdtemp(prefix=f"mah-{task.id}-"))
    try:
        work = tmp / "work"
        base = tmp / "base"  # 수정 전 비교 기준
        shutil.copytree(task.workspace, work)
        shutil.copytree(task.workspace, base)
        shutil.copytree(task.tests, work / "tests")
        if (task.path / "solution").exists():
            shutil.copytree(task.path / "solution", tmp / "_solution")

        error = ""
        start = time.perf_counter()
        try:
            agent.run(work, task.prompt)
        except Exception as exc:  # 에이전트 자체 오류도 결과로 기록
            error = f"{type(exc).__name__}: {exc}"
        duration = time.perf_counter() - start

        passed, total = run_pytest(work)
        files_changed, lines_changed = diff_size(base, work)

        return RunResult(
            task_id=task.id, agent=agent.name,
            passed=passed, total=total,
            files_changed=files_changed, lines_changed=lines_changed,
            duration_s=round(duration, 3), error=error,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

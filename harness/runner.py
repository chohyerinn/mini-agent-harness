"""단일 과제 실행기: 격리된 작업 폴더에서 에이전트를 돌리고 채점한다."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from .agents.base import Agent
from .models import RunResult, Task
from .scoring import compute_diff, run_pytest


def run_task(
    task: Task,
    agent: Agent,
    run_index: int = 1,
    artifact_dir: Path | None = None,
) -> RunResult:
    """task를 임시 폴더에 복제 → 에이전트 실행 → 테스트/수정량 채점.

    `artifact_dir`을 넘기면 이번 실행에 쓰인 prompt, 코드 diff, pytest 로그,
    에러 로그, 메타데이터(실행 시간 등)를 그 폴더에 그대로 남긴다. 회귀가
    "어떤 수정 때문에" 발생했는지 나중에 추적할 수 있게 하기 위함이다.
    """
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
        duration = round(time.perf_counter() - start, 3)

        passed, total, pytest_log = run_pytest(work)
        diff = compute_diff(base, work)

        result = RunResult(
            task_id=task.id, agent=agent.name,
            passed=passed, total=total,
            files_changed=diff.files_changed, lines_changed=diff.lines_changed,
            duration_s=duration, error=error,
            run_index=run_index, artifact_dir=str(artifact_dir) if artifact_dir else "",
        )

        if artifact_dir is not None:
            _save_artifacts(artifact_dir, task, result, diff.text, pytest_log)

        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _save_artifacts(
    artifact_dir: Path, task: Task, result: RunResult, diff_text: str, pytest_log: str,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "prompt.md").write_text(task.prompt, encoding="utf-8")
    (artifact_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
    (artifact_dir / "pytest.log").write_text(pytest_log, encoding="utf-8")
    (artifact_dir / "error.log").write_text(result.error, encoding="utf-8")
    (artifact_dir / "meta.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8",
    )

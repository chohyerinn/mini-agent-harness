"""단일 과제 실행기: 격리된 작업 폴더에서 에이전트를 돌리고 채점한다."""

from __future__ import annotations

import functools
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
import time
from importlib import metadata as _im
from pathlib import Path

from .agents.base import Agent
from .models import RunResult, Task
from .scoring import compute_diff, find_environment_tampering, hash_tree, run_pytest
from .trace import classify_failure, cost_from_trace, normalize_trace, token_usage_from_trace

_ROOT = Path(__file__).resolve().parent.parent


def _git_sha() -> str:
    """harness 저장소의 현재 커밋 SHA(짧은 형식). 워킹트리가 더러우면 `-dirty`.

    git이 없거나 저장소가 아니면 'unknown'을 반환해 실행을 막지 않는다.
    """
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if not sha:
            return "unknown"
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


@functools.lru_cache(maxsize=1)
def runtime_metadata() -> dict:
    """결과를 재현·대조하는 데 필요한 실행 환경 메타데이터.

    같은 점수라도 "어떤 harness 버전 / 어떤 파이썬·의존성에서 나온 결과인지"를
    구분할 수 있도록 meta.json에 함께 남긴다. 프로세스당 한 번만 계산한다.
    """
    def _ver(pkg: str) -> str | None:
        try:
            return _im.version(pkg)
        except Exception:
            return None

    return {
        "harness_commit": _git_sha(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {p: _ver(p) for p in ("pytest", "PyYAML", "anthropic")},
    }


def run_task(
    task: Task,
    agent: Agent,
    run_index: int = 1,
    artifact_dir: Path | None = None,
) -> RunResult:
    """task를 임시 폴더에 복제 → 에이전트 실행 → 테스트/수정량 채점.

    정답 테스트(`tests/`)는 에이전트가 실행을 끝낸 **뒤에만** 작업 폴더에
    넣는다. 에이전트가 미리 테스트를 읽고 답을 맞추거나, 테스트 파일 자체를
    고쳐서 통과시키는 것을 막기 위함이다. 채점 직전에 항상 과제 원본에서
    새로 복사하므로, 에이전트가 그 사이에 `tests/`라는 이름의 폴더를 만들어
    둬도 그대로 덮어써진다. 추가로 conftest.py 등 pytest/파이썬 임포트 동작에
    전역으로 끼어들 수 있는 파일이 새로 생기거나 바뀌었는지, 그리고 정답
    테스트의 해시가 pytest 실행 전후로 같은지 검사해 변조가 의심되면 점수를
    0점으로 강제한다(`RunResult.tamper_detected`).

    `artifact_dir`을 넘기면 이번 실행에 쓰인 prompt, 코드 diff, pytest 로그,
    에러 로그, 메타데이터(실행 시간 등)를 그 폴더에 그대로 남긴다. 회귀가
    "어떤 수정 때문에" 발생했는지 나중에 추적할 수 있게 하기 위함이다.
    """
    tmp = Path(tempfile.mkdtemp(prefix=f"mah-{task.id}-"))
    try:
        work = tmp / "work"
        base = tmp / "base"  # 수정 전 비교 기준(변조 탐지에도 재사용)
        shutil.copytree(task.workspace, work)
        shutil.copytree(task.workspace, base)
        if (task.path / "solution").exists():
            shutil.copytree(task.path / "solution", tmp / "_solution")
        # 주의: 여기서는 tests/를 work에 넣지 않는다 — 에이전트가 아직 못 보게.

        error = ""
        agent_response_text = ""
        stage_durations: dict[str, float] = {}
        total_start = time.perf_counter()
        start = time.perf_counter()
        try:
            agent.run(work, task.prompt)
        except Exception as exc:  # 에이전트 자체 오류도 결과로 기록
            error = f"{type(exc).__name__}: {exc}"
        response_text = getattr(agent, "last_response_text", "")
        if isinstance(response_text, str) and response_text:
            agent_response_text = response_text
        else:
            responses = getattr(agent, "last_responses", "")
            if isinstance(responses, dict):
                agent_response_text = json.dumps(responses, ensure_ascii=False, indent=2)
        duration = round(time.perf_counter() - start, 3)
        stage_durations["agent_run"] = duration
        agent_trace = normalize_trace(getattr(agent, "last_trace", []))
        if not agent_trace:
            agent_trace = [{"step": "agent.run", "duration_s": duration}]
        token_usage = token_usage_from_trace(agent_trace)
        estimated_cost = cost_from_trace(agent_trace)

        start = time.perf_counter()
        tamper_findings = find_environment_tampering(base, work)
        stage_durations["tamper_scan"] = round(time.perf_counter() - start, 3)

        # 채점용 테스트는 지금 처음 넣는다. 에이전트가 미리 같은 이름의
        # 폴더를 만들어 뒀더라도 통째로 지우고 원본에서 새로 복사한다.
        start = time.perf_counter()
        shutil.rmtree(work / "tests", ignore_errors=True)
        shutil.copytree(task.tests, work / "tests")
        tests_hash_ref = hash_tree(task.tests)
        stage_durations["prepare_tests"] = round(time.perf_counter() - start, 3)

        start = time.perf_counter()
        passed, total, pytest_log = run_pytest(work)
        stage_durations["pytest"] = round(time.perf_counter() - start, 3)

        if hash_tree(work / "tests") != tests_hash_ref:
            tamper_findings.append("tests/ 내용이 pytest 실행 전후로 달라짐")

        start = time.perf_counter()
        diff = compute_diff(base, work)
        stage_durations["diff"] = round(time.perf_counter() - start, 3)
        stage_durations["total"] = round(time.perf_counter() - total_start, 3)

        result = RunResult(
            task_id=task.id, agent=agent.name,
            passed=passed, total=total,
            files_changed=diff.files_changed, lines_changed=diff.lines_changed,
            duration_s=duration, error=error,
            run_index=run_index, artifact_dir=str(artifact_dir) if artifact_dir else "",
            prompt_hash=hashlib.sha256(task.prompt.encode()).hexdigest()[:12],
            agent_fingerprint=dict(getattr(agent, "fingerprint", {})),
            agent_trace=agent_trace,
            token_usage=token_usage,
            estimated_cost_usd=estimated_cost,
            stage_durations_s=stage_durations,
            tamper_detected=bool(tamper_findings),
            tamper_reason="; ".join(tamper_findings),
        )
        result.failure_type = classify_failure(result)

        if artifact_dir is not None:
            _save_artifacts(artifact_dir, task, result, diff.text, pytest_log, agent_response_text)

        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _save_artifacts(
    artifact_dir: Path,
    task: Task,
    result: RunResult,
    diff_text: str,
    pytest_log: str,
    agent_response_text: str = "",
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "prompt.md").write_text(task.prompt, encoding="utf-8")
    (artifact_dir / "agent_response.txt").write_text(agent_response_text, encoding="utf-8")
    (artifact_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
    (artifact_dir / "pytest.log").write_text(pytest_log, encoding="utf-8")
    error_log = result.error
    if result.tamper_detected:
        error_log = (error_log + "\n" if error_log else "") + f"[TAMPER DETECTED] {result.tamper_reason}"
    (artifact_dir / "error.log").write_text(error_log, encoding="utf-8")
    meta = {**result.to_dict(), "environment": runtime_metadata()}
    (artifact_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8",
    )

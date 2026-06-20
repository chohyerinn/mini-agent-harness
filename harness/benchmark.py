"""과제 모음(suite)에 대한 벤치마크 및 A/B 비교."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .agents.base import Agent
from .models import RunResult, Task
from .runner import run_task


def load_tasks(tasks_dir: Path) -> list[Task]:
    dirs = [p for p in sorted(Path(tasks_dir).iterdir()) if (p / "task.yaml").exists()]
    return [Task.load(p) for p in dirs]


def run_suite(tasks_dir: Path, agent: Agent) -> list[RunResult]:
    return [run_task(task, agent) for task in load_tasks(tasks_dir)]


def summarize(results: list[RunResult]) -> dict:
    n = len(results)
    solved = sum(r.solved for r in results)
    return {
        "tasks": n,
        "solved": solved,
        "solve_rate": round(solved / n, 4) if n else 0.0,
        "avg_score": round(sum(r.score for r in results) / n, 2) if n else 0.0,
        "avg_pass_rate": round(sum(r.pass_rate for r in results) / n, 4) if n else 0.0,
        "total_duration_s": round(sum(r.duration_s for r in results), 3),
    }


@dataclass
class ABComparison:
    """두 에이전트 설정의 과제별 비교. 회귀(regression) 탐지에 사용."""

    task_id: str
    score_a: float
    score_b: float

    @property
    def delta(self) -> float:
        return round(self.score_b - self.score_a, 2)

    @property
    def regressed(self) -> bool:
        return self.score_b < self.score_a


def compare(results_a: list[RunResult], results_b: list[RunResult]) -> list[ABComparison]:
    by_id_b = {r.task_id: r for r in results_b}
    out = []
    for ra in results_a:
        rb = by_id_b.get(ra.task_id)
        if rb is None:
            continue
        out.append(ABComparison(ra.task_id, ra.score, rb.score))
    return out

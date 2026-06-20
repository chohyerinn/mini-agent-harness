"""과제 모음(suite)에 대한 벤치마크, 반복 실행 통계, A/B 비교."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .agents.base import Agent
from .models import RunResult, Task
from .runner import run_task
from .stats import mean, pass_at_k, stdev


def load_tasks(tasks_dir: Path) -> list[Task]:
    dirs = [p for p in sorted(Path(tasks_dir).iterdir()) if (p / "task.yaml").exists()]
    return [Task.load(p) for p in dirs]


def run_suite(tasks_dir: Path, agent: Agent) -> list[RunResult]:
    """단일 실행(runs=1)의 편의 래퍼."""
    by_task = run_suite_repeated(tasks_dir, agent, runs=1)
    return [reps[0] for reps in by_task.values()]


def run_suite_repeated(
    tasks_dir: Path,
    agent: Agent,
    runs: int = 1,
    artifacts_root: Path | None = None,
) -> dict[str, list[RunResult]]:
    """같은 과제·에이전트 조합을 `runs`번 반복 실행한다.

    각 실행은 독립된 임시 작업 폴더에서 이뤄진다. `artifacts_root`를 넘기면
    실행마다 prompt/diff/pytest 로그/에러 로그/실행 시간을 `<artifacts_root>/<task_id>/run-N/`
    아래에 남겨서, 나중에 "어떤 수정 때문에 실패했는지"를 추적할 수 있게 한다.
    """
    tasks = load_tasks(tasks_dir)
    by_task: dict[str, list[RunResult]] = {}
    for task in tasks:
        reps = []
        for i in range(1, runs + 1):
            artifact_dir = (artifacts_root / task.id / f"run-{i}") if artifacts_root else None
            reps.append(run_task(task, agent, run_index=i, artifact_dir=artifact_dir))
        by_task[task.id] = reps
    return by_task


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
class TaskStats:
    """과제 하나를 `runs`번 반복 실행한 결과에 대한 통계."""

    task_id: str
    runs: int
    solved: int
    scores: list[float]

    @property
    def solve_rate(self) -> float:
        return round(self.solved / self.runs, 4) if self.runs else 0.0

    @property
    def avg_score(self) -> float:
        return round(mean(self.scores), 2)

    @property
    def stdev_score(self) -> float:
        return round(stdev(self.scores), 2)

    @property
    def min_score(self) -> float:
        return min(self.scores) if self.scores else 0.0

    @property
    def max_score(self) -> float:
        return max(self.scores) if self.scores else 0.0

    def pass_at(self, k: int) -> float:
        return round(pass_at_k(self.runs, self.solved, k), 4)

    def to_dict(self, k_values: list[int]) -> dict:
        return {
            "task_id": self.task_id,
            "runs": self.runs,
            "solved": self.solved,
            "solve_rate": self.solve_rate,
            "avg_score": self.avg_score,
            "stdev_score": self.stdev_score,
            "min_score": self.min_score,
            "max_score": self.max_score,
            **{f"pass@{k}": self.pass_at(k) for k in k_values},
        }


def default_k_values(runs: int) -> list[int]:
    """runs 횟수에 맞춰 보여줄 k 목록(1, 5, runs 중 runs 이하인 값만, 중복 제거)."""
    return sorted({k for k in (1, 5, runs) if 1 <= k <= runs})


def task_stats(by_task: dict[str, list[RunResult]]) -> list[TaskStats]:
    out = []
    for task_id, reps in by_task.items():
        scores = [r.score for r in reps]
        solved = sum(r.solved for r in reps)
        out.append(TaskStats(task_id=task_id, runs=len(reps), solved=solved, scores=scores))
    return sorted(out, key=lambda t: t.task_id)


def summarize_repeated(
    by_task: dict[str, list[RunResult]], k_values: list[int] | None = None,
) -> dict:
    """과제별 통계와 전체 평균(overall)을 함께 묶어서 반환한다.

    pass@k는 과제별로 추정한 뒤 과제 전체 평균을 낸다(HumanEval 방식과 동일).
    """
    stats = task_stats(by_task)
    runs = stats[0].runs if stats else 0
    ks = k_values or default_k_values(runs)
    n_tasks = len(stats)
    overall = {
        "tasks": n_tasks,
        "runs_per_task": runs,
        "solve_rate": round(mean([s.solve_rate for s in stats]), 4) if n_tasks else 0.0,
        "avg_score": round(mean([s.avg_score for s in stats]), 2) if n_tasks else 0.0,
        "avg_stdev_score": round(mean([s.stdev_score for s in stats]), 2) if n_tasks else 0.0,
        "min_score": round(min([s.min_score for s in stats]), 2) if n_tasks else 0.0,
        "max_score": round(max([s.max_score for s in stats]), 2) if n_tasks else 0.0,
        **{f"pass@{k}": round(mean([s.pass_at(k) for s in stats]), 4) for k in ks},
    }
    return {"k_values": ks, "overall": overall, "tasks": [s.to_dict(ks) for s in stats]}


@dataclass
class ABComparison:
    """두 에이전트 설정의 과제별 비교(평균 점수 기준). 회귀(regression) 탐지에 사용."""

    task_id: str
    score_a: float
    score_b: float
    stdev_a: float = 0.0
    stdev_b: float = 0.0

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


def compare_repeated(
    by_task_a: dict[str, list[RunResult]], by_task_b: dict[str, list[RunResult]],
) -> list[ABComparison]:
    """반복 실행 결과를 과제별 평균 점수로 비교한다. 표준편차도 함께 남겨서
    "한 번 운 나쁘게 진 것"과 "꾸준히 진 것"을 구분할 수 있게 한다.
    """
    stats_a = {s.task_id: s for s in task_stats(by_task_a)}
    stats_b = {s.task_id: s for s in task_stats(by_task_b)}
    out = []
    for task_id, sa in sorted(stats_a.items()):
        sb = stats_b.get(task_id)
        if sb is None:
            continue
        out.append(ABComparison(task_id, sa.avg_score, sb.avg_score, sa.stdev_score, sb.stdev_score))
    return out

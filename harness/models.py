"""평가에 사용하는 핵심 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Task:
    """하나의 코딩 과제.

    버그가 있는 workspace와 그 버그를 검증하는 tests로 구성된다.
    에이전트는 prompt를 보고 workspace를 수정해 tests를 통과시켜야 한다.
    """

    id: str
    path: Path
    prompt: str
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, task_dir: Path) -> "Task":
        task_dir = Path(task_dir)
        meta = yaml.safe_load((task_dir / "task.yaml").read_text(encoding="utf-8"))
        prompt = (task_dir / "prompt.md").read_text(encoding="utf-8")
        return cls(id=meta["id"], path=task_dir, prompt=prompt, meta=meta)

    @property
    def workspace(self) -> Path:
        return self.path / "workspace"

    @property
    def tests(self) -> Path:
        return self.path / "tests"


@dataclass
class RunResult:
    """에이전트 1회 실행 결과."""

    task_id: str
    agent: str
    passed: int
    total: int
    files_changed: int
    lines_changed: int
    duration_s: float
    error: str = ""
    run_index: int = 1
    artifact_dir: str = ""

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def solved(self) -> bool:
        return self.total > 0 and self.passed == self.total

    @property
    def score(self) -> float:
        """0~100 품질 점수. 통과율이 기본, 과도한 수정에는 소폭 감점."""
        base = self.pass_rate * 100
        penalty = min(10.0, self.lines_changed / 50.0)  # 50줄당 1점, 최대 10점
        return round(max(0.0, base - penalty), 2)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["pass_rate"] = round(self.pass_rate, 4)
        d["solved"] = self.solved
        d["score"] = self.score
        return d

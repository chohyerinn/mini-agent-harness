"""목(mock) 에이전트.

API 키 없이 harness 자체를 검증하고, A/B 비교·반복 실행 통계를 시연하기 위한 에이전트.
- solve: 과제에 동봉된 정답(solution/)을 적용해 테스트를 통과시킨다. (결정론적, 항상 성공)
- noop:  아무것도 하지 않는다. (결정론적, 항상 실패 — 회귀 케이스 시연용)
- flaky: 확률 p로만 정답을 적용한다. (비결정론적 — solve rate, 표준편차, pass@k를
         의미 있게 보여주려면 매번 같은 결과를 내는 에이전트로는 부족하기 때문)
"""

from __future__ import annotations

import random
import shutil
from pathlib import Path


class MockAgent:
    def __init__(self, mode: str = "solve") -> None:
        if mode not in {"solve", "noop"}:
            raise ValueError(f"지원하지 않는 mode: {mode!r}")
        self.mode = mode
        self.name = f"mock:{mode}"

    def run(self, workdir: Path, prompt: str) -> None:
        if self.mode == "noop":
            return
        _apply_solution(workdir)


class FlakyMockAgent:
    """확률 `p`로 정답을 적용하고, 그렇지 않으면 아무것도 하지 않는 에이전트.

    실제 LLM 에이전트처럼 같은 과제를 여러 번 실행해도 매번 결과가 달라지는
    상황을 재현해, --runs 옵션의 solve rate/표준편차/pass@k 통계가 실제로
    의미를 갖도록 만들기 위한 것이다.
    """

    def __init__(self, p: float = 0.5) -> None:
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"성공 확률 p는 0~1 사이여야 함: {p!r}")
        self.p = p
        self.name = f"mock:flaky:{p}" if p != 0.5 else "mock:flaky"
        self._rng = random.Random()

    def run(self, workdir: Path, prompt: str) -> None:
        if self._rng.random() < self.p:
            _apply_solution(workdir)


def _apply_solution(workdir: Path) -> None:
    solution = workdir.parent / "_solution"
    if not solution.exists():
        return
    for src in solution.rglob("*"):
        if src.is_file():
            dst = workdir / src.relative_to(solution)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

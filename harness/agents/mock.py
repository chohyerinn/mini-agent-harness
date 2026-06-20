"""목(mock) 에이전트.

API 키 없이 harness 자체를 검증하고, A/B 비교를 시연하기 위한 결정론적 에이전트.
- solve: 과제에 동봉된 정답(solution/)을 적용해 테스트를 통과시킨다.
- noop:  아무것도 하지 않는다(회귀/실패 케이스 시연용).
"""

from __future__ import annotations

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
        # solve: 과제 폴더의 solution/ 내용을 workdir에 덮어쓴다.
        solution = workdir.parent / "_solution"
        if not solution.exists():
            return
        for src in solution.rglob("*"):
            if src.is_file():
                dst = workdir / src.relative_to(solution)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

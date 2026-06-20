"""에이전트 어댑터 인터페이스."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Agent(Protocol):
    """코딩 에이전트 어댑터.

    harness는 이 인터페이스만 의존한다. 실제 LLM 에이전트든 목(mock)이든
    동일하게 `run`을 구현하면 같은 벤치마크/대시보드로 비교할 수 있다.
    """

    name: str

    def run(self, workdir: Path, prompt: str) -> None:
        """`workdir`의 코드를 `prompt`에 따라 직접 수정한다."""
        ...

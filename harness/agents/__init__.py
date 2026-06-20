"""에이전트 어댑터 모음."""

from .base import Agent
from .mock import FlakyMockAgent, MockAgent


def build_agent(spec: str) -> Agent:
    """스펙 문자열로 에이전트를 생성한다.

    - 'mock:solve' / 'mock:noop' — API 키 없이 도는 목 에이전트
    - 'mock:flaky'      (성공 확률 0.5)
    - 'mock:flaky:0.3'  (성공 확률 0.3)
    - 'claude' / 'claude:<model>' — 실제 Claude 에이전트 (기본 claude-opus-4-8,
      ANTHROPIC_API_KEY 필요)

    다른 LLM도 Agent 프로토콜만 구현해 여기에 분기를 추가하면 된다.
    """
    kind, _, rest = spec.partition(":")

    if kind == "claude":
        from .claude import ClaudeAgent

        return ClaudeAgent(model=rest or "claude-opus-4-8")

    if kind != "mock":
        raise ValueError(f"알 수 없는 에이전트: {spec!r}")

    mode, _, p_str = rest.partition(":")
    mode = mode or "solve"
    if mode == "flaky":
        return FlakyMockAgent(p=float(p_str) if p_str else 0.5)
    return MockAgent(mode=mode)

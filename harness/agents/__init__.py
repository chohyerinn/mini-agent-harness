"""에이전트 어댑터 모음."""

from .base import Agent
from .mock import FlakyMockAgent, MockAgent


def build_agent(spec: str) -> Agent:
    """스펙 문자열로 에이전트를 생성한다.

    - 'mock:solve' / 'mock:noop' — API 키 없이 도는 목 에이전트
    - 'mock:flaky'      (성공 확률 0.5)
    - 'mock:flaky:0.3'  (성공 확률 0.3)
    - 'clova' / 'clova:<model>' — 실제 CLOVA Studio 에이전트 (기본 HCX-005)
    - 'multi' / 'multi:clova' / 'multi:clova:<model>' — CLOVA Planner/Coder/Reviewer
    - 'claude' / 'claude:<model>' — 선택적 Claude 에이전트
    - 'multi:claude:<model>' — 선택적 Claude Planner/Coder/Reviewer

    다른 LLM도 Agent 프로토콜만 구현해 여기에 분기를 추가하면 된다.
    """
    kind, _, rest = spec.partition(":")

    if kind == "claude":
        from .claude import ClaudeAgent

        return ClaudeAgent(model=rest or "claude-opus-4-8")

    if kind == "clova":
        from .clova import ClovaAgent

        return ClovaAgent(model=rest or "HCX-005")

    if kind == "multi":
        if rest == "claude" or rest.startswith("claude:") or rest.startswith("claude-"):
            from .multi import MultiClaudeAgent

            if rest == "claude":
                model = "claude-opus-4-8"
            elif rest.startswith("claude:"):
                model = rest.split(":", 1)[1] or "claude-opus-4-8"
            else:
                model = rest
            return MultiClaudeAgent(model=model)

        from .clova import MultiClovaAgent

        model = rest or "clova"
        if model == "clova":
            model = "HCX-005"
        elif model.startswith("clova:"):
            model = model.split(":", 1)[1] or "HCX-005"
        return MultiClovaAgent(model=model)

    if kind != "mock":
        raise ValueError(f"알 수 없는 에이전트: {spec!r}")

    mode, _, p_str = rest.partition(":")
    mode = mode or "solve"
    if mode == "flaky":
        return FlakyMockAgent(p=float(p_str) if p_str else 0.5)
    return MockAgent(mode=mode)

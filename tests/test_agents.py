from harness.agents import build_agent


def test_build_multi_agent_default_model():
    agent = build_agent("multi")
    assert agent.name.startswith("multi:")
    assert agent.fingerprint["pattern"] == "planner-coder-reviewer"


def test_build_multi_agent_explicit_model():
    agent = build_agent("multi:claude-sonnet-4-0")
    assert agent.name == "multi:claude-sonnet-4-0"

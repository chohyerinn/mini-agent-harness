from harness.agents import build_agent
from harness.agents.clova import ClovaAgent, ClovaChatClient, MultiClovaAgent


def test_build_multi_agent_default_model():
    agent = build_agent("multi")
    assert agent.name == "multi:clova:HCX-005"
    assert agent.fingerprint["pattern"] == "planner-coder-reviewer"
    assert agent.fingerprint["provider"] == "clova-studio"


def test_build_multi_agent_explicit_model():
    agent = build_agent("multi:clova:HCX-DASH-002")
    assert agent.name == "multi:clova:HCX-DASH-002"


def test_build_multi_agent_keeps_legacy_claude_spec():
    agent = build_agent("multi:claude-sonnet-4-0")
    assert agent.name == "multi:claude-sonnet-4-0"


def test_build_clova_agent_default_model():
    agent = build_agent("clova")
    assert agent.name == "clova:HCX-005"
    assert agent.fingerprint["provider"] == "clova-studio"


def test_clova_client_uses_openai_compatible_payload():
    calls = []

    def fake_transport(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return {
            "choices": [{"message": {"content": "<review>pass</review>"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }

    client = ClovaChatClient(
        api_key="test-key",
        model="HCX-005",
        base_url="https://example.com/v1/openai",
        transport=fake_transport,
        timeout=3,
    )
    text, usage = client.complete("system", "user")

    assert text == "<review>pass</review>"
    assert usage == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
    url, headers, payload, timeout = calls[0]
    assert url == "https://example.com/v1/openai/chat/completions"
    assert headers["Authorization"] == "Bearer test-key"
    assert payload["model"] == "HCX-005"
    assert payload["messages"][0]["role"] == "system"
    assert timeout == 3


def test_clova_agent_applies_file_blocks(tmp_path):
    class FakeClient:
        def complete(self, system, user):
            return (
                '<file path="m.py">\ndef f():\n    return 42\n</file>',
                {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            )

    (tmp_path / "m.py").write_text("def f():\n    return 0\n", encoding="utf-8")
    agent = ClovaAgent(client=FakeClient())
    agent.run(tmp_path, "make f return 42")

    assert (tmp_path / "m.py").read_text(encoding="utf-8") == "def f():\n    return 42\n"
    assert agent.last_trace[0]["step"] == "clova.edit"
    assert agent.last_trace[0]["files_written"] == 1


def test_multi_clova_agent_records_planner_coder_reviewer(tmp_path):
    class FakeClient:
        def __init__(self):
            self.responses = iter([
                ("Plan: change m.f.", {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}),
                (
                    '<file path="m.py">\ndef f():\n    return 42\n</file>',
                    {"input_tokens": 5, "output_tokens": 6, "total_tokens": 11},
                ),
                ("<review>pass</review>", {"input_tokens": 7, "output_tokens": 8, "total_tokens": 15}),
            ])

        def complete(self, system, user):
            return next(self.responses)

    (tmp_path / "m.py").write_text("def f():\n    return 0\n", encoding="utf-8")
    agent = MultiClovaAgent(client=FakeClient())
    agent.run(tmp_path, "make f return 42")

    assert (tmp_path / "m.py").read_text(encoding="utf-8") == "def f():\n    return 42\n"
    assert [step["step"] for step in agent.last_trace] == ["planner", "coder", "reviewer"]
    assert agent.last_trace[1]["files_written"] == 1
    assert agent.last_trace[2]["review_passed"] is True

"""run_task 통합 테스트: 격리·변조 0점 처리·아티팩트.

임시 과제(workspace/solution/tests)를 그때그때 만들어, harness가 에이전트를
어떻게 격리하고 채점하는지를 종단으로 검증한다.
"""

import json
from pathlib import Path

from harness.agents.mock import MockAgent
from harness.models import Task
from harness.runner import run_task


def _make_task(tmp_path: Path) -> Task:
    """f()가 42를 반환해야 통과하는 최소 과제. 버그 버전은 0을 반환한다."""
    t = tmp_path / "task"
    (t / "workspace").mkdir(parents=True)
    (t / "workspace" / "m.py").write_text("def f():\n    return 0\n", encoding="utf-8")
    (t / "solution").mkdir()
    (t / "solution" / "m.py").write_text("def f():\n    return 42\n", encoding="utf-8")
    (t / "tests").mkdir()
    (t / "tests" / "test_m.py").write_text(
        "from m import f\n\n\ndef test_f():\n    assert f() == 42\n", encoding="utf-8"
    )
    (t / "task.yaml").write_text("id: tmp-task\n", encoding="utf-8")
    (t / "prompt.md").write_text("f가 42를 반환하도록 고치세요.\n", encoding="utf-8")
    return Task.load(t)


def test_solve_passes(tmp_path):
    task = _make_task(tmp_path)
    r = run_task(task, MockAgent("solve"))
    assert (r.passed, r.total) == (1, 1)
    assert r.solved is True
    assert r.score > 0
    assert r.tamper_detected is False


def test_noop_fails(tmp_path):
    task = _make_task(tmp_path)
    r = run_task(task, MockAgent("noop"))
    assert r.passed == 0
    assert r.solved is False


def test_tests_not_visible_during_agent_run(tmp_path):
    """핵심 격리 속성: agent.run()이 도는 동안 tests/는 작업 폴더에 없어야 한다."""
    task = _make_task(tmp_path)

    class _Spy:
        name = "spy"

        def __init__(self):
            self.saw_tests = None

        def run(self, workdir, prompt):
            self.saw_tests = (workdir / "tests").exists()

    spy = _Spy()
    run_task(task, spy)
    assert spy.saw_tests is False


def test_planted_tests_are_overwritten(tmp_path):
    """에이전트가 가짜 통과 테스트를 tests/에 심어 둬도 원본으로 덮어쓴다."""
    task = _make_task(tmp_path)

    class _Planter:
        name = "planter"

        def run(self, workdir, prompt):
            (workdir / "tests").mkdir(exist_ok=True)
            (workdir / "tests" / "test_m.py").write_text(
                "def test_fake():\n    assert True\n", encoding="utf-8"
            )
            # 진짜 버그(0 반환)는 고치지 않는다.

    r = run_task(task, _Planter())
    # 원본 테스트가 복원돼 실제로는 실패해야 한다.
    assert r.solved is False
    assert r.passed == 0


def test_environment_tampering_forces_zero(tmp_path):
    """conftest.py로 결과를 조작하려 하면 변조로 감지하고 0점 처리한다."""
    task = _make_task(tmp_path)

    class _Tamper:
        name = "tamper"

        def run(self, workdir, prompt):
            (workdir / "conftest.py").write_text(
                "def pytest_collection_modifyitems(config, items):\n    items.clear()\n",
                encoding="utf-8",
            )

    r = run_task(task, _Tamper())
    assert r.tamper_detected is True
    assert r.score == 0.0
    assert r.solved is False
    assert "conftest.py" in r.tamper_reason


def test_artifacts_include_environment_metadata(tmp_path):
    task = _make_task(tmp_path)
    art = tmp_path / "art"
    run_task(task, MockAgent("solve"), artifact_dir=art)
    for name in ("prompt.md", "agent_response.txt", "diff.patch", "pytest.log", "error.log", "meta.json"):
        assert (art / name).exists(), name
    meta = json.loads((art / "meta.json").read_text(encoding="utf-8"))
    assert meta["solved"] is True
    # 실행 환경 메타데이터(harness 커밋·파이썬·의존성)가 함께 기록돼야 한다.
    env = meta["environment"]
    assert "harness_commit" in env
    assert "python" in env
    assert "packages" in env
    assert meta["agent_trace"][0]["step"] == "agent.run"
    assert "token_usage" in meta
    assert "estimated_cost_usd" in meta
    assert "stage_durations_s" in meta
    assert meta["failure_type"] == "solved"


def test_artifacts_include_agent_trace_and_cost(tmp_path):
    task = _make_task(tmp_path)

    class _TraceAgent:
        name = "trace-agent"
        fingerprint = {"kind": "test"}

        def run(self, workdir, prompt):
            self.last_response_text = '<file path="m.py">...</file>'
            self.last_trace = [{
                "step": "planner",
                "duration_s": 0.12,
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "estimated_cost_usd": 0.001,
            }]
            (workdir / "m.py").write_text("def f():\n    return 42\n", encoding="utf-8")

    art = tmp_path / "trace-art"
    run_task(task, _TraceAgent(), artifact_dir=art)
    meta = json.loads((art / "meta.json").read_text(encoding="utf-8"))
    assert meta["agent_trace"][0]["step"] == "planner"
    assert meta["token_usage"]["input_tokens"] == 10
    assert meta["token_usage"]["output_tokens"] == 5
    assert meta["estimated_cost_usd"] == 0.001
    assert meta["agent_fingerprint"] == {"kind": "test"}
    assert (art / "agent_response.txt").read_text(encoding="utf-8") == '<file path="m.py">...</file>'

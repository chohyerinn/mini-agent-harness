"""회귀 판정(verdict)과 반복 실행 집계 테스트.

"평균이 낮다"와 "통계적으로 확정된 회귀"를 구분하는 로직이 이 도구의 핵심
주장이므로, 판정 분기를 빠짐없이 못박는다.
"""

import math

from harness.benchmark import (
    TaskStats,
    _verdict,
    compare_repeated,
    default_k_values,
    summarize_repeated,
)
from harness.models import RunResult


def _run(passed: int) -> RunResult:
    """lines_changed=0이라 점수는 통과율 그대로(통과=100, 실패=0)인 결과."""
    return RunResult(
        task_id="t", agent="x", passed=passed, total=1,
        files_changed=0, lines_changed=0, duration_s=0.0,
    )


# --- _verdict 분기 --------------------------------------------------------

def test_verdict_insufficient_data_when_too_few_runs():
    assert _verdict(1, 5, -10, -20, -1) == "insufficient_data"
    assert _verdict(5, 1, -10, -20, -1) == "insufficient_data"


def test_verdict_confirmed_regression():
    # CI 전체가 0 미만 → 확정 회귀
    assert _verdict(5, 5, -10, -20, -5) == "regression"


def test_verdict_confirmed_improvement():
    # CI 전체가 0 초과 → 확정 개선
    assert _verdict(5, 5, 10, 5, 20) == "improvement"


def test_verdict_regression_candidate_when_ci_straddles_zero():
    # 평균은 떨어졌지만 CI가 0을 걸침 → 후보
    assert _verdict(5, 5, -10, -20, 5) == "regression_candidate"


def test_verdict_improvement_candidate_when_ci_straddles_zero():
    assert _verdict(5, 5, 10, -5, 20) == "improvement_candidate"


def test_verdict_no_difference():
    assert _verdict(5, 5, 0, -5, 5) == "no_difference"


# --- TaskStats ------------------------------------------------------------

def test_task_stats_solve_rate_and_pass_at_k():
    ts = TaskStats(task_id="t", runs=5, solved=1, scores=[100.0, 0.0, 0.0, 0.0, 0.0])
    assert ts.solve_rate == 0.2
    assert math.isclose(ts.pass_at(1), 0.2)
    assert math.isclose(ts.pass_at(5), 1.0)
    assert ts.min_score == 0.0
    assert ts.max_score == 100.0


def test_task_stats_to_dict_has_pass_at_columns():
    ts = TaskStats(task_id="t", runs=5, solved=5, scores=[100.0] * 5)
    d = ts.to_dict([1, 5])
    assert d["pass@1"] == 1.0
    assert d["pass@5"] == 1.0
    assert d["solve_rate"] == 1.0


# --- default_k_values -----------------------------------------------------

def test_default_k_values():
    assert default_k_values(1) == [1]
    assert default_k_values(3) == [1, 3]
    assert default_k_values(5) == [1, 5]
    assert default_k_values(10) == [1, 5, 10]


# --- summarize_repeated / compare_repeated --------------------------------

def test_summarize_repeated_all_solved():
    by_task = {"t": [_run(1) for _ in range(5)]}
    s = summarize_repeated(by_task)
    assert s["overall"]["solve_rate"] == 1.0
    assert s["overall"]["pass@1"] == 1.0


def test_compare_repeated_confirms_regression():
    a = {"t": [_run(1) for _ in range(5)]}   # 항상 100
    b = {"t": [_run(0) for _ in range(5)]}   # 항상 0
    comps = compare_repeated(a, b)
    assert len(comps) == 1
    assert comps[0].verdict == "regression"
    assert comps[0].regressed is True


def test_compare_repeated_insufficient_with_single_run():
    a = {"t": [_run(1)]}
    b = {"t": [_run(0)]}
    comps = compare_repeated(a, b)
    assert comps[0].verdict == "insufficient_data"
    assert comps[0].regressed is False

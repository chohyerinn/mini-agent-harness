from harness.models import RunResult
from harness.trace import efficiency_summary, failure_counts, response_recovery_counts


def _result(**kwargs):
    defaults = dict(
        task_id="t",
        agent="clova",
        passed=1,
        total=1,
        files_changed=1,
        lines_changed=1,
        duration_s=1.0,
        token_usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 100},
        stage_durations_s={"agent_run": 2.0},
    )
    defaults.update(kwargs)
    return RunResult(**defaults)


def test_efficiency_summary_counts_tokens_and_seconds_per_solved():
    results = [
        _result(token_usage={"total_tokens": 100}, stage_durations_s={"agent_run": 2.0}),
        _result(passed=0, total=1, token_usage={"total_tokens": 50}, stage_durations_s={"agent_run": 3.0}),
        _result(token_usage={"total_tokens": 150}, stage_durations_s={"agent_run": 5.0}),
    ]

    summary = efficiency_summary(results)

    assert summary["runs"] == 3
    assert summary["solved"] == 2
    assert summary["solve_rate"] == 0.6667
    assert summary["total_tokens"] == 300
    assert summary["agent_seconds"] == 10.0
    assert summary["tokens_per_solved"] == 150.0
    assert summary["seconds_per_solved"] == 5.0


def test_response_recovery_counts_fenced_fallbacks_and_reasons():
    results = [
        _result(agent_trace=[{
            "step": "clova.edit",
            "response_recovery": {
                "used_fenced_code_fallback": True,
                "reason": "single_file_python_fence",
            },
        }]),
        _result(agent_trace=[{
            "step": "clova.edit",
            "response_recovery": {
                "used_fenced_code_fallback": False,
                "reason": "explicit_file_blocks",
            },
        }]),
    ]

    assert response_recovery_counts(results) == {
        "fenced_code_fallback": 1,
        "reason:explicit_file_blocks": 1,
        "reason:single_file_python_fence": 1,
    }


def test_failure_counts_labels_multi_reviewer_edge_case():
    result = _result(
        agent="multi:clova:HCX-005",
        passed=1,
        total=2,
        agent_trace=[{"step": "reviewer", "review_passed": True}],
    )

    assert failure_counts([result]) == {"reviewer_missed_edge_case": 1}

"""반복 실행 리포트(Markdown + JSON) 생성."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .benchmark import ABComparison, SuiteComparison, compare_repeated, compare_suite, summarize_repeated
from .models import RunResult
from .trace import aggregate_trace, efficiency_summary, failure_counts, response_recovery_counts


def _pct(x: float) -> str:
    return f"{x:.0%}"


def _format_p_value(p: float) -> str:
    if p < 0.0001:
        return "<0.0001"
    return f"{p:.4f}".rstrip("0").rstrip(".")


def _task_rows(tasks: list[dict], k_values: list[int]) -> str:
    out = []
    for t in sorted(tasks, key=lambda x: x["avg_score"], reverse=True):
        pass_cols = " | ".join(_pct(t[f"pass@{k}"]) for k in k_values)
        out.append(
            f"| {t['task_id']} | {t['runs']} | {t['solved']}/{t['runs']} | "
            f"{_pct(t['solve_rate'])} | {t['avg_score']} | {t['stdev_score']} | "
            f"{t['min_score']} | {t['max_score']} | {pass_cols} |"
        )
    return "\n".join(out)


def _all_results(by_task: dict[str, list[RunResult]]) -> list[RunResult]:
    return [r for reps in by_task.values() for r in reps]


def _trace_markdown(results: list[RunResult]) -> str:
    trace = aggregate_trace(results)
    usage = trace["token_usage"]
    efficiency = efficiency_summary(results)
    rows = "\n".join(
        f"| {s['step']} | {s['runs']} | {s['duration_s']} | {s['avg_duration_s']} | "
        f"${s['estimated_cost_usd']:.6f} |"
        for s in trace["steps"]
    ) or "| - | 0 | 0 | 0 | $0.000000 |"
    return f"""## Trace / cost

| Metric | Value |
|---|---|
| input tokens | {usage['input_tokens']} |
| output tokens | {usage['output_tokens']} |
| total tokens | {usage['total_tokens']} |
| estimated cost | ${trace['estimated_cost_usd']:.6f} |
| tokens / solved run | {efficiency['tokens_per_solved']} |
| sec / solved run | {efficiency['seconds_per_solved']} |

| Step | runs | total sec | avg sec | estimated cost |
|---|---:|---:|---:|---:|
{rows}
"""


def _failure_markdown(results: list[RunResult]) -> str:
    counts = failure_counts(results)
    rows = "\n".join(f"| {k} | {v} |" for k, v in sorted(counts.items())) or "| - | 0 |"
    return f"""## Failure types

| Type | runs |
|---|---:|
{rows}
"""


def _response_recovery_markdown(results: list[RunResult]) -> str:
    counts = response_recovery_counts(results)
    fallback = counts.get("fenced_code_fallback", 0)
    reasons = {
        k.removeprefix("reason:"): v
        for k, v in counts.items()
        if k.startswith("reason:")
    }
    rows = "\n".join(f"| {k} | {v} |" for k, v in sorted(reasons.items())) or "| - | 0 |"
    return f"""## Response recovery

| Metric | Value |
|---|---:|
| fenced code fallback applied | {fallback} |

| Reason | runs |
|---|---:|
{rows}
"""


def _overall_ab_summary(
    results_a: list[RunResult],
    results_b: list[RunResult],
    comps: list[ABComparison],
) -> dict[str, int | float]:
    eff_a = efficiency_summary(results_a)
    eff_b = efficiency_summary(results_b)
    return {
        "a_solved": eff_a["solved"],
        "b_solved": eff_b["solved"],
        "a_runs": eff_a["runs"],
        "b_runs": eff_b["runs"],
        "a_solve_rate": eff_a["solve_rate"],
        "b_solve_rate": eff_b["solve_rate"],
        "a_tokens": eff_a["total_tokens"],
        "b_tokens": eff_b["total_tokens"],
        "a_agent_seconds": eff_a["agent_seconds"],
        "b_agent_seconds": eff_b["agent_seconds"],
        "a_tokens_per_solved": eff_a["tokens_per_solved"],
        "b_tokens_per_solved": eff_b["tokens_per_solved"],
        "a_seconds_per_solved": eff_a["seconds_per_solved"],
        "b_seconds_per_solved": eff_b["seconds_per_solved"],
        "confirmed_improvements": sum(1 for c in comps if c.verdict == "improvement"),
        "confirmed_regressions": sum(1 for c in comps if c.verdict == "regression"),
        "improvement_candidates": sum(1 for c in comps if c.verdict == "improvement_candidate"),
        "regression_candidates": sum(1 for c in comps if c.verdict == "regression_candidate"),
    }


def _ab_summary_markdown(summary: dict[str, int | float]) -> str:
    return f"""## Overall summary

| Metric | A | B |
|---|---:|---:|
| solved runs | {summary['a_solved']}/{summary['a_runs']} | {summary['b_solved']}/{summary['b_runs']} |
| solve rate | {_pct(float(summary['a_solve_rate']))} | {_pct(float(summary['b_solve_rate']))} |
| total tokens | {summary['a_tokens']} | {summary['b_tokens']} |
| agent seconds | {summary['a_agent_seconds']} | {summary['b_agent_seconds']} |
| tokens / solved run | {summary['a_tokens_per_solved']} | {summary['b_tokens_per_solved']} |
| sec / solved run | {summary['a_seconds_per_solved']} | {summary['b_seconds_per_solved']} |

| Verdict | Count |
|---|---:|
| confirmed improvements | {summary['confirmed_improvements']} |
| confirmed regressions | {summary['confirmed_regressions']} |
| improvement candidates | {summary['improvement_candidates']} |
| regression candidates | {summary['regression_candidates']} |
"""


def write_repeated_markdown(
    by_task: dict[str, list[RunResult]],
    out_dir: Path,
    agent: str,
    k_values: list[int] | None = None,
) -> Path:
    """과제별 solve rate, 평균 점수, 표준편차, 최소/최대, pass@k를 담은 리포트를 작성한다."""
    summary = summarize_repeated(by_task, k_values)
    ks = summary["k_values"]
    o = summary["overall"]
    today = dt.date.today().isoformat()
    results = _all_results(by_task)

    pass_header = " | ".join(f"pass@{k}" for k in ks)
    pass_overall_rows = "\n".join(f"| pass@{k} (평균) | {_pct(o[f'pass@{k}'])} |" for k in ks)

    md = f"""# 반복 실행 리포트 — {today}

**에이전트:** `{agent}`  **과제당 실행 횟수:** {o['runs_per_task']}

pass@k는 "과제당 k번을 시도하면 적어도 한 번은 성공할 확률"의 불편추정량이다
(자세한 정의는 README 참고). 아래 표의 pass@k는 과제별로 추정한 값을 전체
과제에 대해 평균한 것이다.

## 전체 요약

| 지표 | 값 |
|---|---|
| 과제 수 | {o['tasks']} |
| 평균 solve rate | {_pct(o['solve_rate'])} |
| 평균 점수 | {o['avg_score']} |
| 평균 표준편차 | {o['avg_stdev_score']} |
| 최소 점수 | {o['min_score']} |
| 최대 점수 | {o['max_score']} |
{pass_overall_rows}

## 과제별 결과

| Task | 실행 | 해결 | solve rate | 평균 점수 | 표준편차 | 최소 | 최대 | {pass_header} |
|---|---|---|---|---|---|---|---|{'---|' * len(ks)}
{_task_rows(summary['tasks'], ks)}

{_trace_markdown(results)}

{_failure_markdown(results)}

{_response_recovery_markdown(results)}
"""
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_agent = agent.replace(":", "_")
    path = out_dir / f"report-{today}-{safe_agent}.md"
    path.write_text(md, encoding="utf-8")
    (out_dir / f"report-{today}-{safe_agent}.json").write_text(
        json.dumps(
            {
                "agent": agent,
                "summary": summary,
                "trace": aggregate_trace(results),
                "efficiency": efficiency_summary(results),
                "failure_types": failure_counts(results),
                "response_recovery": response_recovery_counts(results),
                "runs": {
                    task_id: [r.to_dict() for r in reps] for task_id, reps in by_task.items()
                },
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return path


_VERDICT_LABEL = {
    "regression": "🔻 회귀(확정)",
    "regression_candidate": "🔶 회귀 후보(유의성 부족)",
    "improvement": "🔺 개선(확정)",
    "improvement_candidate": "🔸 개선 후보(유의성 부족)",
    "no_difference": "➖ 차이 없음",
    "insufficient_data": "❔ 표본 부족",
}

_SUITE_VERDICT_LABEL = {
    "significant_improvement": "🔺 유의한 개선",
    "significant_regression": "🔻 유의한 회귀",
    "improvement_not_significant": "🔸 개선 방향이나 유의하지 않음",
    "regression_not_significant": "🔶 회귀 방향이나 유의하지 않음",
    "no_difference": "➖ 차이 없음",
    "insufficient_data": "❔ 표본 부족",
}


def _suite_significance_markdown(suite: SuiteComparison) -> str:
    """suite 전체 solve rate 차이의 유의성과 한계비용 섹션.

    헤드라인 '49% → 58%'가 통계적으로 유의한지, 그리고 더 푼 1건당 토큰을
    얼마나 더 썼는지를 한눈에 보여준다.
    """
    label = _SUITE_VERDICT_LABEL.get(suite.verdict, suite.verdict)
    marginal = suite.marginal_tokens_per_extra_solve
    p_value = _format_p_value(suite.mcnemar_p)
    marginal_row = (
        f"| 한계비용(추가 1건 해결당 토큰) | {marginal:,.0f} |"
        if suite.solved_b > suite.solved_a
        else "| 한계비용(추가 1건 해결당 토큰) | — (B가 더 풀지 못함) |"
    )
    return f"""## Suite 차원 유의성 (solve rate)

과제별 점수 CI와 별개로, 헤드라인 지표인 *전체 solve rate* 차이가 통계적으로
유의한지 따로 검정한다. 두 설정이 같은 과제 집합을 풀므로 과제 단위 페어드
부트스트랩 CI와 (과제, run) 짝 McNemar 검정을 함께 본다.

| Metric | Value |
|---|---:|
| solve rate A → B | {suite.solve_rate_a:.0%} → {suite.solve_rate_b:.0%} ({suite.diff:+.0%}) |
| 페어드 부트스트랩 95% CI (B−A) | [{suite.ci_low:+.3f}, {suite.ci_high:+.3f}] |
| McNemar 불일치쌍 (A만/B만 성공) | {suite.only_a_solved} / {suite.only_b_solved} |
| McNemar 검정 통계량 / p | {suite.mcnemar_stat} / {p_value} |
| 판정 | **{label}** |
{marginal_row}

> CI가 0을 포함하거나 p가 크면, solve rate가 올라 *보여도* 표본으로는 우연과
> 구분할 수 없다는 뜻이다. 이때 추가 토큰 비용은 정당화하기 어렵다.
"""


def write_ab_repeated_markdown(
    by_task_a: dict[str, list[RunResult]],
    by_task_b: dict[str, list[RunResult]],
    out_dir: Path,
    agent_a: str,
    agent_b: str,
) -> Path:
    """두 에이전트(또는 두 설정)의 과제별 점수를 비교한다.

    평균 점수가 낮다고 바로 "회귀"라고 쓰지 않는다. 부트스트랩 신뢰구간이
    0 미만에 완전히 들어가야 "회귀(확정)"이고, 평균은 떨어졌지만 신뢰구간이
    0을 걸치면 "회귀 후보"로만 표시한다 — 표본 5회 정도로는 우연한 차이일
    수 있기 때문이다(자세한 설명은 README 참고).
    """
    comps = compare_repeated(by_task_a, by_task_b)
    today = dt.date.today().isoformat()
    results_a = _all_results(by_task_a)
    results_b = _all_results(by_task_b)
    confirmed_regressions = [c for c in comps if c.verdict == "regression"]
    confirmed_improvements = [c for c in comps if c.verdict == "improvement"]
    candidate_regressions = [c for c in comps if c.verdict == "regression_candidate"]
    insufficient = [c for c in comps if c.verdict == "insufficient_data"]
    overall = _overall_ab_summary(results_a, results_b, comps)
    suite = compare_suite(by_task_a, by_task_b)

    rows = "\n".join(
        f"| {c.task_id} | {c.score_a} ± {c.stdev_a} (n={c.n_a}) | "
        f"{c.score_b} ± {c.stdev_b} (n={c.n_b}) | {c.delta:+} | "
        f"[{c.ci_low:+}, {c.ci_high:+}] | {_VERDICT_LABEL.get(c.verdict, c.verdict)} |"
        for c in comps
    )

    note = ""
    if insufficient:
        note = (
            f"\n> ⚠️ {len(insufficient)}개 과제는 `--runs`가 2 미만이라 신뢰구간을 "
            "추정할 수 없습니다(`insufficient_data`). 통계적으로 뒷받침된 판정을 "
            "보려면 `--runs 5` 이상으로 다시 실행하세요.\n"
        )

    md = f"""# A/B 비교 — {today}

**A (기준):** `{agent_a}`  **B (후보):** `{agent_b}`

CI는 `mean(B) - mean(A)`에 대한 95% 부트스트랩 신뢰구간이다. 신뢰구간이
0을 포함하면("후보") 표본 크기로는 우연한 차이와 구분할 수 없다는 뜻이고,
0 미만/초과에 완전히 들어가야("확정") 통계적으로 뒷받침된 차이로 본다.
그래서 평균 점수 차이만으로 회귀나 개선을 단정하지 않는다.
{note}
확정 개선: **{len(confirmed_improvements)}건**  ·  확정 회귀: **{len(confirmed_regressions)}건**  ·  회귀 후보(유의성 부족): **{len(candidate_regressions)}건**  ·  전체 {len(comps)}건

{_ab_summary_markdown(overall)}

{_suite_significance_markdown(suite)}

| Task | A 평균±표준편차 | B 평균±표준편차 | Δ | 95% CI(B-A) | 판정 |
|---|---|---|---|---|---|
{rows}

## A trace / cost

{_trace_markdown(results_a)}

{_failure_markdown(results_a)}

{_response_recovery_markdown(results_a)}

## B trace / cost

{_trace_markdown(results_b)}

{_failure_markdown(results_b)}

{_response_recovery_markdown(results_b)}
"""
    if confirmed_improvements:
        md += "\n## 🔺 확정된 개선\n" + "\n".join(
            f"- `{c.task_id}` ({c.score_a} → {c.score_b}, {c.delta:+}, "
            f"95% CI [{c.ci_low:+}, {c.ci_high:+}])"
            for c in confirmed_improvements
        ) + "\n"
    if confirmed_regressions:
        md += "\n## 🔻 확정된 회귀\n" + "\n".join(
            f"- `{c.task_id}` ({c.score_a} → {c.score_b}, {c.delta:+}, "
            f"95% CI [{c.ci_low:+}, {c.ci_high:+}])"
            for c in confirmed_regressions
        ) + "\n"
    if candidate_regressions:
        md += "\n## 🔶 회귀 후보 (통계적으로 확정되지 않음)\n" + "\n".join(
            f"- `{c.task_id}` ({c.score_a} → {c.score_b}, {c.delta:+}, "
            f"95% CI [{c.ci_low:+}, {c.ci_high:+}]이 0을 포함)"
            for c in candidate_regressions
        ) + "\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"ab-{today}-{agent_a.replace(':', '_')}-vs-{agent_b.replace(':', '_')}.md"
    path.write_text(md, encoding="utf-8")
    return path

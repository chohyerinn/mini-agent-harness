"""반복 실행 리포트(Markdown + JSON) 생성."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .benchmark import ABComparison, compare_repeated, summarize_repeated
from .models import RunResult
from .trace import aggregate_trace, failure_counts


def _pct(x: float) -> str:
    return f"{x:.0%}"


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
                "failure_types": failure_counts(results),
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
    candidate_regressions = [c for c in comps if c.verdict == "regression_candidate"]
    insufficient = [c for c in comps if c.verdict == "insufficient_data"]

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
정의는 README의 "회귀 판정 방법" 절 참고.
{note}
확정된 회귀: **{len(confirmed_regressions)}건**  ·  회귀 후보(유의성 부족): **{len(candidate_regressions)}건**  ·  전체 {len(comps)}건

| Task | A 평균±표준편차 | B 평균±표준편차 | Δ | 95% CI(B-A) | 판정 |
|---|---|---|---|---|---|
{rows}

## A trace / cost

{_trace_markdown(results_a)}

{_failure_markdown(results_a)}

## B trace / cost

{_trace_markdown(results_b)}

{_failure_markdown(results_b)}
"""
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

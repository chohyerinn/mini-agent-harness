"""반복 실행 리포트(Markdown + JSON) 생성."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .benchmark import ABComparison, compare_repeated, summarize_repeated
from .models import RunResult


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
                "runs": {
                    task_id: [r.to_dict() for r in reps] for task_id, reps in by_task.items()
                },
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_ab_repeated_markdown(
    by_task_a: dict[str, list[RunResult]],
    by_task_b: dict[str, list[RunResult]],
    out_dir: Path,
    agent_a: str,
    agent_b: str,
) -> Path:
    """두 에이전트(또는 두 설정)의 과제별 평균 점수를 비교해 회귀를 찾는다."""
    comps = compare_repeated(by_task_a, by_task_b)
    today = dt.date.today().isoformat()
    regressions = [c for c in comps if c.regressed]
    rows = "\n".join(
        f"| {c.task_id} | {c.score_a} ± {c.stdev_a} | {c.score_b} ± {c.stdev_b} | "
        f"{'🔻' if c.regressed else '➖' if c.delta == 0 else '🔺'} {c.delta:+} |"
        for c in comps
    )
    md = f"""# A/B 회귀 테스트 — {today}

**A (기준):** `{agent_a}`  **B (후보):** `{agent_b}`

회귀 발생: **{len(regressions)}건** / 전체 {len(comps)}건

| Task | A 평균±표준편차 | B 평균±표준편차 | Δ |
|---|---|---|---|
{rows}
"""
    if regressions:
        md += "\n## ⚠️ 회귀 과제\n" + "\n".join(
            f"- `{c.task_id}` ({c.score_a} → {c.score_b}, {c.delta:+})" for c in regressions
        ) + "\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"ab-{today}-{agent_a.replace(':', '_')}-vs-{agent_b.replace(':', '_')}.md"
    path.write_text(md, encoding="utf-8")
    return path

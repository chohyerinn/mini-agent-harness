"""일간 품질 리포트(대시보드) 생성: Markdown + 단일 HTML."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .benchmark import ABComparison, summarize
from .models import RunResult


def _rows(results: list[RunResult]) -> str:
    out = []
    for r in sorted(results, key=lambda x: x.score, reverse=True):
        mark = "✅" if r.solved else "❌"
        out.append(
            f"| {r.task_id} | {mark} | {r.passed}/{r.total} | "
            f"{r.score} | {r.files_changed} | {r.lines_changed} | {r.duration_s}s |"
        )
    return "\n".join(out)


def write_markdown(results: list[RunResult], out_dir: Path, agent: str) -> Path:
    s = summarize(results)
    today = dt.date.today().isoformat()
    md = f"""# 품질 리포트 — {today}

**에이전트:** `{agent}`

| 지표 | 값 |
|---|---|
| 과제 수 | {s['tasks']} |
| 해결 | {s['solved']} ({s['solve_rate']:.0%}) |
| 평균 점수 | {s['avg_score']} |
| 평균 통과율 | {s['avg_pass_rate']:.0%} |
| 총 소요 | {s['total_duration_s']}s |

## 과제별 결과

| Task | 해결 | 통과 | 점수 | 변경파일 | 변경라인 | 시간 |
|---|---|---|---|---|---|---|
{_rows(results)}
"""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"report-{today}.md"
    path.write_text(md, encoding="utf-8")
    (out_dir / f"report-{today}.json").write_text(
        json.dumps({"agent": agent, "summary": s,
                    "results": [r.to_dict() for r in results]},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_ab_markdown(comps: list[ABComparison], out_dir: Path,
                      agent_a: str, agent_b: str) -> Path:
    today = dt.date.today().isoformat()
    regressions = [c for c in comps if c.regressed]
    rows = "\n".join(
        f"| {c.task_id} | {c.score_a} | {c.score_b} | "
        f"{'🔻' if c.regressed else '➖' if c.delta == 0 else '🔺'} {c.delta:+} |"
        for c in comps
    )
    md = f"""# A/B 회귀 테스트 — {today}

**A (기준):** `{agent_a}`  **B (후보):** `{agent_b}`

회귀 발생: **{len(regressions)}건** / 전체 {len(comps)}건

| Task | A 점수 | B 점수 | Δ |
|---|---|---|---|
{rows}
"""
    if regressions:
        md += "\n## ⚠️ 회귀 과제\n" + "\n".join(
            f"- `{c.task_id}` ({c.score_a} → {c.score_b}, {c.delta:+})" for c in regressions
        ) + "\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"ab-{today}.md"
    path.write_text(md, encoding="utf-8")
    return path

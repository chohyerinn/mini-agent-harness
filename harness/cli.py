"""커맨드라인 진입점.

예시:
  python -m harness.cli run --agent mock:solve --runs 5
  python -m harness.cli ab  --a mock:solve --b mock:noop --runs 5
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from .agents import build_agent
from .benchmark import compare_repeated, run_suite_repeated, summarize_repeated
from .report import write_ab_repeated_markdown, write_repeated_markdown

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS = ROOT / "tasks"
DEFAULT_OUT = ROOT / "reports"


def _timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _safe(name: str) -> str:
    return name.replace(":", "_")


def cmd_run(args: argparse.Namespace) -> None:
    agent = build_agent(args.agent)
    out_dir = Path(args.out)
    artifacts_root = out_dir / "runs" / f"{_timestamp()}_{_safe(agent.name)}"

    by_task = run_suite_repeated(Path(args.tasks), agent, runs=args.runs, artifacts_root=artifacts_root)
    summary = summarize_repeated(by_task)
    o = summary["overall"]
    pass_str = ", ".join(f"pass@{k}={o[f'pass@{k}']:.0%}" for k in summary["k_values"])
    print(
        f"[{agent.name}] runs={args.runs} · solve rate {o['solve_rate']:.0%} · "
        f"평균점수 {o['avg_score']} (±{o['avg_stdev_score']}) · {pass_str}"
    )
    path = write_repeated_markdown(by_task, out_dir, agent.name)
    print(f"리포트: {path}")
    print(f"실행별 아티팩트: {artifacts_root}")


def cmd_ab(args: argparse.Namespace) -> None:
    agent_a, agent_b = build_agent(args.a), build_agent(args.b)
    tasks = Path(args.tasks)
    out_dir = Path(args.out)
    ts = _timestamp()
    root_a = out_dir / "runs" / f"{ts}_ab_{_safe(agent_a.name)}-vs-{_safe(agent_b.name)}" / _safe(agent_a.name)
    root_b = out_dir / "runs" / f"{ts}_ab_{_safe(agent_a.name)}-vs-{_safe(agent_b.name)}" / _safe(agent_b.name)

    by_task_a = run_suite_repeated(tasks, agent_a, runs=args.runs, artifacts_root=root_a)
    by_task_b = run_suite_repeated(tasks, agent_b, runs=args.runs, artifacts_root=root_b)

    write_repeated_markdown(by_task_a, out_dir, agent_a.name)
    write_repeated_markdown(by_task_b, out_dir, agent_b.name)

    path = write_ab_repeated_markdown(by_task_a, by_task_b, out_dir, agent_a.name, agent_b.name)
    comps = compare_repeated(by_task_a, by_task_b)
    confirmed = [c for c in comps if c.verdict == "regression"]
    candidates = [c for c in comps if c.verdict == "regression_candidate"]
    print(
        f"A={agent_a.name}  B={agent_b.name}  runs={args.runs}  "
        f"확정된 회귀 {len(confirmed)}/{len(comps)}건 · 회귀 후보(유의성 부족) {len(candidates)}건"
    )
    if args.runs < 2:
        print("주의: --runs가 2 미만이라 모든 과제가 'insufficient_data'로 표시됩니다. --runs 5 이상을 권장합니다.")
    print(f"리포트: {path}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="mini-agent-harness")
    p.add_argument("--tasks", default=str(DEFAULT_TASKS))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="단일 에이전트 벤치마크")
    pr.add_argument("--agent", default="mock:solve")
    pr.add_argument("--runs", type=int, default=1, help="과제당 반복 실행 횟수 (기본 1)")
    pr.set_defaults(func=cmd_run)

    pa = sub.add_parser("ab", help="두 에이전트 A/B 회귀 비교")
    pa.add_argument("--a", default="mock:solve")
    pa.add_argument("--b", default="mock:noop")
    pa.add_argument("--runs", type=int, default=1, help="과제당 반복 실행 횟수 (기본 1)")
    pa.set_defaults(func=cmd_ab)

    args = p.parse_args(argv)
    if args.runs < 1:
        p.error("--runs는 1 이상이어야 합니다")
    args.func(args)


if __name__ == "__main__":
    main()

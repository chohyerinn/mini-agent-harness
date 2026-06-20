"""커맨드라인 진입점.

예시:
  python -m harness.cli run --agent mock:solve
  python -m harness.cli ab  --a mock:solve --b mock:noop
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .agents import build_agent
from .benchmark import compare, run_suite, summarize
from .report import write_ab_markdown, write_markdown

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS = ROOT / "tasks"
DEFAULT_OUT = ROOT / "reports"


def cmd_run(args: argparse.Namespace) -> None:
    agent = build_agent(args.agent)
    results = run_suite(Path(args.tasks), agent)
    s = summarize(results)
    print(f"[{agent.name}] 해결 {s['solved']}/{s['tasks']} "
          f"({s['solve_rate']:.0%}) · 평균점수 {s['avg_score']}")
    path = write_markdown(results, Path(args.out), agent.name)
    print(f"리포트: {path}")


def cmd_ab(args: argparse.Namespace) -> None:
    agent_a, agent_b = build_agent(args.a), build_agent(args.b)
    tasks = Path(args.tasks)
    results_a = run_suite(tasks, agent_a)
    results_b = run_suite(tasks, agent_b)
    comps = compare(results_a, results_b)
    regressions = [c for c in comps if c.regressed]
    print(f"A={agent_a.name}  B={agent_b.name}  회귀 {len(regressions)}/{len(comps)}건")
    path = write_ab_markdown(comps, Path(args.out), agent_a.name, agent_b.name)
    print(f"리포트: {path}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="mini-agent-harness")
    p.add_argument("--tasks", default=str(DEFAULT_TASKS))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="단일 에이전트 벤치마크")
    pr.add_argument("--agent", default="mock:solve")
    pr.set_defaults(func=cmd_run)

    pa = sub.add_parser("ab", help="두 에이전트 A/B 회귀 비교")
    pa.add_argument("--a", default="mock:solve")
    pa.add_argument("--b", default="mock:noop")
    pa.set_defaults(func=cmd_ab)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

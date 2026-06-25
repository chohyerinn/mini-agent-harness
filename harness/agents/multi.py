"""Multi-agent Claude adapter.

The harness still sees a single `Agent.run(workdir, prompt)` call.  Internally
this adapter splits the work into Planner, Coder, and Reviewer Claude calls and
records a per-step trace for later A/B comparison.
"""

from __future__ import annotations

import time
from pathlib import Path

from .claude import (
    _FILE_BLOCK,
    _read_sources,
    _response_text,
    _usage_dict,
    estimate_anthropic_cost_usd,
)


PLANNER_SYSTEM = """\
You are the planner in a coding-agent team.
Read the task and current source files. Produce a short implementation plan.
Do not output code. Do not mention tests you cannot see. Keep the plan specific.
"""

CODER_SYSTEM = """\
You are the coder in a coding-agent team.
Use the task, source files, and planner notes to fix the bug.
Return the full new content of every file you change, each wrapped as:

<file path="relative/path.py">
...complete file content...
</file>

Output only these <file> blocks. No prose, no markdown fences.
"""

REVIEWER_SYSTEM = """\
You are the reviewer in a coding-agent team.
Review the current source files after the coder's patch.
If a small correction is needed, return full replacement files in <file> blocks.
If no correction is needed, return:

<review>pass</review>

Do not output markdown fences.
"""


def _files_blob(workdir: Path) -> str:
    sources = _read_sources(workdir)
    return "\n\n".join(f'<file path="{path}">\n{body}</file>' for path, body in sources.items())


def _apply_file_blocks(workdir: Path, text: str) -> int:
    changed = 0
    for match in _FILE_BLOCK.finditer(text):
        rel = Path(match.group("path"))
        if rel.is_absolute() or ".." in rel.parts:
            continue
        dst = workdir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(match.group("body"), encoding="utf-8")
        changed += 1
    return changed


class MultiClaudeAgent:
    MAX_TOKENS = 16000

    def __init__(self, model: str = "claude-opus-4-8") -> None:
        self.model = model
        self.name = f"multi:{model}"
        self.last_trace: list[dict] = []
        self.last_responses: dict[str, str] = {}
        self.fingerprint = {
            "model": model,
            "max_tokens": self.MAX_TOKENS,
            "pattern": "planner-coder-reviewer",
            "steps": ["planner", "coder", "reviewer"],
        }

    def _call(self, client, step: str, system: str, user: str) -> str:
        start = time.perf_counter()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.MAX_TOKENS,
            system=system,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": user}],
        )
        duration = round(time.perf_counter() - start, 3)
        text = _response_text(response)
        usage = _usage_dict(response)
        self.last_trace.append({
            "step": step,
            "model": self.model,
            "duration_s": duration,
            **usage,
            "estimated_cost_usd": estimate_anthropic_cost_usd(
                self.model, usage["input_tokens"], usage["output_tokens"]
            ),
            "response_chars": len(text),
        })
        self.last_responses[step] = text
        return text

    def run(self, workdir: Path, prompt: str) -> None:
        import anthropic

        self.fingerprint["sdk"] = getattr(anthropic, "__version__", "unknown")
        self.last_trace = []
        self.last_responses = {}
        client = anthropic.Anthropic()

        files = _files_blob(workdir)
        planner_user = f"# Task\n{prompt}\n\n# Current files\n{files}"
        plan = self._call(client, "planner", PLANNER_SYSTEM, planner_user)

        coder_user = f"# Task\n{prompt}\n\n# Planner notes\n{plan}\n\n# Current files\n{files}"
        coder_text = self._call(client, "coder", CODER_SYSTEM, coder_user)
        coder_files = _apply_file_blocks(workdir, coder_text)
        if self.last_trace:
            self.last_trace[-1]["files_written"] = coder_files

        reviewer_files = _files_blob(workdir)
        reviewer_user = (
            f"# Task\n{prompt}\n\n# Planner notes\n{plan}\n\n"
            f"# Current files after coder patch\n{reviewer_files}"
        )
        reviewer_text = self._call(client, "reviewer", REVIEWER_SYSTEM, reviewer_user)
        reviewer_writes = _apply_file_blocks(workdir, reviewer_text)
        if self.last_trace:
            self.last_trace[-1]["files_written"] = reviewer_writes
            self.last_trace[-1]["review_passed"] = reviewer_writes == 0 and "<review>pass</review>" in reviewer_text

"""Trace, token, cost, and failure summaries for agent runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .models import RunResult


def normalize_trace(raw: Any) -> list[dict[str, Any]]:
    """Return a JSON-safe list of trace step dictionaries.

    Agents may expose `last_trace` as a best-effort debugging aid.  The runner
    should never fail because a custom agent put an odd object in that field.
    """
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        step = str(item.get("step") or f"step-{i}")
        normalized: dict[str, Any] = {"step": step}
        for key, value in item.items():
            if key == "step":
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                normalized[key] = value
            elif isinstance(value, (list, dict)):
                normalized[key] = value
            else:
                normalized[key] = str(value)
        if "duration_s" in normalized:
            try:
                normalized["duration_s"] = round(float(normalized["duration_s"]), 3)
            except (TypeError, ValueError):
                normalized.pop("duration_s", None)
        if "estimated_cost_usd" in normalized and normalized["estimated_cost_usd"] is not None:
            try:
                normalized["estimated_cost_usd"] = round(float(normalized["estimated_cost_usd"]), 6)
            except (TypeError, ValueError):
                normalized.pop("estimated_cost_usd", None)
        out.append(normalized)
    return out


def token_usage_from_trace(trace: list[dict[str, Any]]) -> dict[str, int]:
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for step in trace:
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = step.get(key)
            if isinstance(value, int):
                usage[key] += value
    if usage["total_tokens"] == 0:
        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
    return usage


def cost_from_trace(trace: list[dict[str, Any]]) -> float:
    total = 0.0
    for step in trace:
        value = step.get("estimated_cost_usd")
        if isinstance(value, (int, float)):
            total += float(value)
    return round(total, 6)


def classify_failure(result: RunResult) -> str:
    """Coarse failure type used for reports.

    This is intentionally conservative.  It should help reviewers see where a
    run broke without pretending to be a perfect root-cause classifier.
    """
    if result.solved:
        return "solved"
    if result.tamper_detected:
        return "tamper"
    if result.error:
        return "agent_error"
    if result.files_changed == 0:
        return "planning_error"
    if result.passed > 0:
        return "partial_implementation"
    if result.agent.startswith("multi:") and any(
        str(step.get("step", "")).lower().startswith("review") for step in result.agent_trace
    ):
        return "reviewer_miss"
    return "implementation_error"


def aggregate_trace(results: list[RunResult]) -> dict[str, Any]:
    by_step: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"runs": 0, "duration_s": 0.0, "estimated_cost_usd": 0.0}
    )
    token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for result in results:
        for key in token_usage:
            token_usage[key] += int(result.token_usage.get(key, 0))
        for step in result.agent_trace:
            name = str(step.get("step") or "unknown")
            row = by_step[name]
            row["runs"] = int(row["runs"]) + 1
            row["duration_s"] = float(row["duration_s"]) + float(step.get("duration_s") or 0.0)
            row["estimated_cost_usd"] = float(row["estimated_cost_usd"]) + float(
                step.get("estimated_cost_usd") or 0.0
            )
    return {
        "token_usage": token_usage,
        "estimated_cost_usd": round(sum(r.estimated_cost_usd for r in results), 6),
        "steps": [
            {
                "step": step,
                "runs": int(row["runs"]),
                "duration_s": round(float(row["duration_s"]), 3),
                "avg_duration_s": round(float(row["duration_s"]) / int(row["runs"]), 3)
                if row["runs"] else 0.0,
                "estimated_cost_usd": round(float(row["estimated_cost_usd"]), 6),
            }
            for step, row in sorted(by_step.items())
        ],
    }


def failure_counts(results: list[RunResult]) -> dict[str, int]:
    return dict(Counter(r.failure_type or classify_failure(r) for r in results))

"""CLOVA Studio coding-agent adapters.

The default path uses CLOVA Studio's OpenAI-compatible chat endpoint:
``https://clovastudio.stream.ntruss.com/v1/openai/chat/completions``.

Required at runtime:
  - CLOVASTUDIO_API_KEY, or CLOVA_API_KEY

Optional:
  - CLOVA_MODEL, default HCX-005
  - CLOVA_BASE_URL, default https://clovastudio.stream.ntruss.com/v1/openai
  - CLOVA_MAX_TOKENS, default 4096
  - CLOVA_TEMPERATURE, default 0
  - CLOVA_TIMEOUT, default 120
  - CLOVA_MAX_RETRIES, default 3
  - CLOVA_RETRY_BASE_DELAY, default 2.0
  - CLOVA_INPUT_PRICE_PER_MTOK / CLOVA_OUTPUT_PRICE_PER_MTOK for local cost estimates
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .coding_io import apply_agent_response_with_recovery, files_blob

DEFAULT_MODEL = "HCX-005"
DEFAULT_BASE_URL = "https://clovastudio.stream.ntruss.com/v1/openai"
DEFAULT_MAX_TOKENS = 4096

SYSTEM = """\
You are a coding agent fixing a bug in a small Python project.
Edit only what the task requires. Keep changes minimal.
Do not add examples, demos, print statements, decorators, CLI code, or unrelated parameters.
Return the full new content of every file you change, each wrapped as:

<file path="relative/path.py">
...complete file content...
</file>

Output only these <file> blocks. No prose, no markdown fences.

중요:
- 설명하지 말고 수정한 파일 전체 내용만 출력하세요.
- Markdown 코드블록(```python)은 절대 쓰지 마세요.
- 파일을 고쳤다면 반드시 <file path="..."> 형식으로 감싸세요."""

PLANNER_SYSTEM = """\
You are the planner in a coding-agent team.
Read the task and current source files. Produce a short implementation plan.
Do not output code. Do not mention tests you cannot see. Keep the plan specific.
"""

CODER_SYSTEM = """\
You are the coder in a coding-agent team.
Use the task, source files, and planner notes to fix the bug.
Do not add examples, demos, print statements, decorators, CLI code, or unrelated parameters.
Return the full new content of every file you change, each wrapped as:

<file path="relative/path.py">
...complete file content...
</file>

Output only these <file> blocks. No prose, no markdown fences.

중요:
- 설명하지 말고 수정한 파일 전체 내용만 출력하세요.
- Markdown 코드블록(```python)은 절대 쓰지 마세요.
- 파일을 고쳤다면 반드시 <file path="..."> 형식으로 감싸세요.
"""

REVIEWER_SYSTEM = """\
You are the reviewer in a coding-agent team.
Review the current source files after the coder's patch.
If a small correction is needed, return full replacement files in <file> blocks.
If no correction is needed, return:

<review>pass</review>

Do not output markdown fences.
"""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _chat_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _default_post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    max_retries = _env_int("CLOVA_MAX_RETRIES", 3)
    base_delay = _env_float("CLOVA_RETRY_BASE_DELAY", 2.0)

    for attempt in range(max_retries + 1):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < max_retries:
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else base_delay * (2 ** attempt)
                except ValueError:
                    delay = base_delay * (2 ** attempt)
                time.sleep(min(delay, 30.0))
                continue
            raise RuntimeError(f"CLOVA Studio API failed: HTTP {exc.code} {detail}") from exc

    raise RuntimeError("CLOVA Studio API failed after retries")


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _response_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        if isinstance(choice, dict):
            message = choice.get("message")
            if isinstance(message, dict):
                return _content_to_text(message.get("content"))
            return _content_to_text(choice.get("text"))
    result = data.get("result")
    if isinstance(result, dict):
        message = result.get("message")
        if isinstance(message, dict):
            return _content_to_text(message.get("content"))
        return _content_to_text(result.get("content"))
    return ""


def _usage_dict(data: dict[str, Any]) -> dict[str, int]:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        result = data.get("result")
        usage = result.get("usage") if isinstance(result, dict) else {}
    if not isinstance(usage, dict):
        usage = {}

    input_tokens = int(
        usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or usage.get("inputTokens")
        or 0
    )
    output_tokens = int(
        usage.get("completion_tokens")
        or usage.get("output_tokens")
        or usage.get("outputTokens")
        or 0
    )
    total_tokens = int(usage.get("total_tokens") or usage.get("totalTokens") or 0)
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def estimate_clova_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Best-effort local estimate when price env vars are provided.

    CLOVA Studio billing can vary by plan/model.  The adapter therefore avoids
    hard-coding a price table and records zero unless explicit local rates are
    set through environment variables.
    """
    input_price = _env_float("CLOVA_INPUT_PRICE_PER_MTOK", 0.0)
    output_price = _env_float("CLOVA_OUTPUT_PRICE_PER_MTOK", 0.0)
    return round(
        (input_tokens / 1_000_000) * input_price
        + (output_tokens / 1_000_000) * output_price,
        6,
    )


def _single_user_prompt(prompt: str, current_files: str) -> str:
    return f"""\
# Task
{prompt}

# Current files
{current_files}

# Required output format
수정이 필요한 파일의 전체 내용을 아래 형식으로만 출력하세요.

<file path="relative/path.py">
...complete file content...
</file>

규칙:
- 설명 문장, 요약, 마크다운 코드블록을 출력하지 마세요.
- 테스트 파일은 수정하지 마세요.
- 필요한 최소 코드만 고치세요.
- 예제 실행 코드, print 디버깅, __main__ 블록을 추가하지 마세요.
"""


def _coder_user_prompt(prompt: str, plan: str, current_files: str) -> str:
    return f"""\
# Task
{prompt}

# Planner notes
{plan}

# Current files
{current_files}

# Required output format
수정이 필요한 파일의 전체 내용을 아래 형식으로만 출력하세요.

<file path="relative/path.py">
...complete file content...
</file>

규칙:
- 설명 문장, 요약, 마크다운 코드블록을 출력하지 마세요.
- 테스트 파일은 수정하지 마세요.
- 필요한 최소 코드만 고치세요.
- 예제 실행 코드, print 디버깅, __main__ 블록을 추가하지 마세요.
"""


class ClovaChatClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: int | None = None,
        transport: Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]
        | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("CLOVASTUDIO_API_KEY") or os.environ.get("CLOVA_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "CLOVA Studio API key is missing. Set CLOVASTUDIO_API_KEY or CLOVA_API_KEY."
            )
        self.model = model or os.environ.get("CLOVA_MODEL") or DEFAULT_MODEL
        self.base_url = base_url or os.environ.get("CLOVA_BASE_URL") or DEFAULT_BASE_URL
        self.endpoint = _chat_endpoint(self.base_url)
        self.max_tokens = max_tokens if max_tokens is not None else _env_int("CLOVA_MAX_TOKENS", DEFAULT_MAX_TOKENS)
        self.temperature = (
            temperature if temperature is not None else _env_float("CLOVA_TEMPERATURE", 0.0)
        )
        self.timeout = timeout if timeout is not None else _env_int("CLOVA_TIMEOUT", 120)
        self.transport = transport or _default_post_json

    def complete(self, system: str, user: str) -> tuple[str, dict[str, int]]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = self.transport(self.endpoint, headers, payload, self.timeout)
        return _response_text(data), _usage_dict(data)


class ClovaAgent:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        client: ClovaChatClient | None = None,
    ) -> None:
        self.model = model
        self.client = client
        self.name = f"clova:{model}"
        self.last_trace: list[dict[str, Any]] = []
        self.last_response_text = ""
        self.fingerprint = {
            "provider": "clova-studio",
            "model": model,
            "max_tokens": _env_int("CLOVA_MAX_TOKENS", DEFAULT_MAX_TOKENS),
        }

    def _client(self) -> ClovaChatClient:
        if self.client is None:
            self.client = ClovaChatClient(model=self.model)
        return self.client

    def run(self, workdir: Path, prompt: str) -> None:
        user = _single_user_prompt(prompt, files_blob(workdir))
        start = time.perf_counter()
        text, usage = self._client().complete(SYSTEM, user)
        duration = round(time.perf_counter() - start, 3)
        self.last_response_text = text
        self.last_trace = [{
            "step": "clova.edit",
            "provider": "clova-studio",
            "model": self.model,
            "duration_s": duration,
            **usage,
            "estimated_cost_usd": estimate_clova_cost_usd(
                usage["input_tokens"], usage["output_tokens"]
            ),
            "response_chars": len(text),
        }]
        applied = apply_agent_response_with_recovery(workdir, text)
        self.last_trace[-1]["files_written"] = applied.files_written
        self.last_trace[-1]["response_recovery"] = applied.recovery


class MultiClovaAgent:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        client: ClovaChatClient | None = None,
    ) -> None:
        self.model = model
        self.client = client
        self.name = f"multi:clova:{model}"
        self.last_trace: list[dict[str, Any]] = []
        self.last_responses: dict[str, str] = {}
        self.fingerprint = {
            "provider": "clova-studio",
            "model": model,
            "max_tokens": _env_int("CLOVA_MAX_TOKENS", DEFAULT_MAX_TOKENS),
            "pattern": "planner-coder-reviewer",
            "steps": ["planner", "coder", "reviewer"],
        }

    def _client(self) -> ClovaChatClient:
        if self.client is None:
            self.client = ClovaChatClient(model=self.model)
        return self.client

    def _call(self, step: str, system: str, user: str) -> str:
        start = time.perf_counter()
        text, usage = self._client().complete(system, user)
        duration = round(time.perf_counter() - start, 3)
        self.last_trace.append({
            "step": step,
            "provider": "clova-studio",
            "model": self.model,
            "duration_s": duration,
            **usage,
            "estimated_cost_usd": estimate_clova_cost_usd(
                usage["input_tokens"], usage["output_tokens"]
            ),
            "response_chars": len(text),
        })
        self.last_responses[step] = text
        return text

    def run(self, workdir: Path, prompt: str) -> None:
        self.last_trace = []
        self.last_responses = {}

        files = files_blob(workdir)
        planner_user = f"# Task\n{prompt}\n\n# Current files\n{files}"
        plan = self._call("planner", PLANNER_SYSTEM, planner_user)

        coder_user = _coder_user_prompt(prompt, plan, files)
        coder_text = self._call("coder", CODER_SYSTEM, coder_user)
        coder_applied = apply_agent_response_with_recovery(workdir, coder_text)
        if self.last_trace:
            self.last_trace[-1]["files_written"] = coder_applied.files_written
            self.last_trace[-1]["response_recovery"] = coder_applied.recovery

        reviewer_files = files_blob(workdir)
        reviewer_user = (
            f"# Task\n{prompt}\n\n# Planner notes\n{plan}\n\n"
            f"# Current files after coder patch\n{reviewer_files}"
        )
        reviewer_text = self._call("reviewer", REVIEWER_SYSTEM, reviewer_user)
        reviewer_applied = apply_agent_response_with_recovery(workdir, reviewer_text)
        if self.last_trace:
            self.last_trace[-1]["files_written"] = reviewer_applied.files_written
            self.last_trace[-1]["response_recovery"] = reviewer_applied.recovery
            self.last_trace[-1]["review_passed"] = (
                reviewer_applied.files_written == 0 and "<review>pass</review>" in reviewer_text
            )

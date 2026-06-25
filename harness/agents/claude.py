"""Claude(Anthropic) 코딩 에이전트 어댑터.

workdir의 소스를 읽어 프롬프트와 함께 Claude에 전달하고, 응답으로 받은
수정 파일을 다시 workdir에 기록한다. mock과 동일한 Agent 인터페이스를
구현하므로 같은 벤치마크/대시보드로 비교할 수 있다.

환경 변수 ANTHROPIC_API_KEY 필요. anthropic 패키지는 이 에이전트를 쓸 때만
설치하면 된다(`pip install anthropic`).
"""

from __future__ import annotations

import re
import time
from pathlib import Path

_FILE_BLOCK = re.compile(r'<file path="(?P<path>[^"]+)">\n?(?P<body>.*?)</file>', re.DOTALL)

SYSTEM = """\
You are a coding agent fixing a bug in a small Python project.
Edit only what the task requires. Keep changes minimal.
Return the full new content of every file you change, each wrapped as:

<file path="relative/path.py">
...complete file content...
</file>

Output only these <file> blocks. No prose, no markdown fences."""


_PRICE_PER_MTOK = {
    # Approximate public list prices. Override with environment-specific
    # accounting if exact billing is needed.
    "haiku": (0.80, 4.00),
    "sonnet": (3.00, 15.00),
    "opus": (15.00, 75.00),
}


def estimate_anthropic_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    model_l = model.lower()
    prices = next((v for k, v in _PRICE_PER_MTOK.items() if k in model_l), None)
    if prices is None:
        return 0.0
    input_per_mtok, output_per_mtok = prices
    return round((input_tokens / 1_000_000) * input_per_mtok + (output_tokens / 1_000_000) * output_per_mtok, 6)


def _response_text(response) -> str:
    return "".join(b.text for b in response.content if getattr(b, "type", "") == "text")


def _usage_dict(response) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _read_sources(workdir: Path) -> dict[str, str]:
    """tests/ 와 내부 파일을 제외한 소스 파일을 {상대경로: 내용}으로 읽는다."""
    sources: dict[str, str] = {}
    for p in sorted(workdir.rglob("*.py")):
        rel = p.relative_to(workdir)
        if rel.parts[0] in {"tests"} or any(part.startswith("_") for part in rel.parts):
            continue
        sources[str(rel).replace("\\", "/")] = p.read_text(encoding="utf-8")
    return sources


class ClaudeAgent:
    MAX_TOKENS = 16000

    def __init__(self, model: str = "claude-opus-4-8") -> None:
        self.model = model
        self.name = f"claude:{model}"
        self.last_trace: list[dict] = []
        self.last_response_text = ""
        # 실행 메타데이터: meta.json의 agent_fingerprint로 그대로 기록된다.
        # 어떤 모델 설정으로 받은 결과인지 나중에 재현·대조할 수 있게 한다.
        # sdk 버전은 anthropic을 임포트한 뒤 run()에서 채운다.
        self.fingerprint = {
            "model": model,
            "max_tokens": self.MAX_TOKENS,
            "thinking": "adaptive",
        }

    def run(self, workdir: Path, prompt: str) -> None:
        import anthropic  # 지연 임포트: claude 에이전트를 쓸 때만 필요

        self.fingerprint["sdk"] = getattr(anthropic, "__version__", "unknown")

        sources = _read_sources(workdir)
        files_blob = "\n\n".join(
            f'<file path="{path}">\n{body}</file>' for path, body in sources.items()
        )
        user = f"# Task\n{prompt}\n\n# Current files\n{files_blob}"

        client = anthropic.Anthropic()
        start = time.perf_counter()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.MAX_TOKENS,
            system=SYSTEM,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": user}],
        )
        duration = round(time.perf_counter() - start, 3)
        text = _response_text(response)
        usage = _usage_dict(response)
        self.last_response_text = text
        self.last_trace = [{
            "step": "claude.edit",
            "model": self.model,
            "duration_s": duration,
            **usage,
            "estimated_cost_usd": estimate_anthropic_cost_usd(
                self.model, usage["input_tokens"], usage["output_tokens"]
            ),
            "response_chars": len(text),
        }]

        for m in _FILE_BLOCK.finditer(text):
            rel = Path(m.group("path"))
            if rel.is_absolute() or ".." in rel.parts:  # 경로 탈출 방지
                continue
            dst = workdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(m.group("body"), encoding="utf-8")

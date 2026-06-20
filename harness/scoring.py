"""테스트 실행, 변조 탐지, 수정 규모 측정."""

from __future__ import annotations

import difflib
import hashlib
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

IGNORED_TOP_LEVEL = {"tests", "_solution"}

# pytest 서브프로세스에 넘길 환경 변수 화이트리스트.
# 에이전트가 호출하는 LLM API 키(ANTHROPIC_API_KEY 등) 같은 비밀값이
# 과제 코드(테스트로 실행되는 워크스페이스)에서 os.environ으로 새어 나가지
# 않도록, 전체 os.environ을 그대로 물려주지 않고 꼭 필요한 키만 화이트리스트로
# 골라 넘긴다. 거부(deny) 목록 방식은 새로운 비밀 키 이름을 놓치기 쉬워서
# 허용(allow) 목록 방식을 쓴다.
_ALLOWED_ENV_KEYS = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA",
    "LANG", "LC_ALL", "PYTHONUTF8", "PYTHONIOENCODING",
}

# pytest/파이썬의 임포트·실행 동작에 전역으로 끼어들 수 있는 파일 이름.
# 에이전트가 이런 파일을 새로 만들거나 고치면, 진짜 버그를 고치지 않고도
# 테스트 결과 자체를 조작할 수 있다(예: assert를 무력화하는 conftest.py).
#
# pyproject.toml도 [tool.pytest.ini_options]로 pytest 동작을 바꿀 수 있어 포함한다.
# 또 채점 서브프로세스의 PYTHONPATH에 워크스페이스가 들어가므로, pytest/pluggy
# 같은 모듈을 같은 이름의 파일로 가려(shadow) 동작을 바꿀 수 있다 — 흔한
# shadowing 이름도 막는다. 사전(unchanged) 파일은 before/after 비교에서 걸리지
# 않으므로, 워크스페이스에 원래 있던 설정 파일은 오탐하지 않는다.
HOOK_FILENAMES = {
    "conftest.py", "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg",
    "sitecustomize.py", "usercustomize.py",
    "pytest.py", "pluggy.py", "py.py", "_pytest.py",
}


def _sandboxed_env(workdir: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() in _ALLOWED_ENV_KEYS}
    env["PYTHONPATH"] = str(workdir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # 문자열 해시 무작위화(PYTHONHASHSEED)가 매 서브프로세스마다 달라지면
    # set()/dict() 순서에 의존하는 코드의 테스트 결과가 같은 코드인데도
    # 실행마다 달라진다. --runs로 측정하려는 건 "에이전트의 변동성"이지
    # "채점 환경의 변동성"이 아니므로 고정한다.
    env["PYTHONHASHSEED"] = "0"
    return env


def run_pytest(workdir: Path) -> tuple[int, int, str]:
    """workdir에서 pytest를 돌리고 (passed, total, log)를 반환한다.

    junit-xml로 결과를 파싱해 통과/전체 개수를 정확히 세고,
    stdout+stderr는 합쳐서 로그 텍스트로 그대로 보존한다(아티팩트 저장용).
    서브프로세스 환경 변수는 화이트리스트만 물려준다(`_sandboxed_env`).
    """
    report = workdir / "_junit.xml"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests",
             "--junitxml", str(report), "-q", "-p", "no:cacheprovider"],
            cwd=workdir, env=_sandboxed_env(workdir),
            capture_output=True, text=True,
            timeout=300,
        )
        log = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        log = f"pytest timeout: {exc}"

    if not report.exists():
        return 0, 0, log
    root = ET.parse(report).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        return 0, 0, log
    total = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    passed = total - failures - errors - skipped
    return passed, total, log


def hash_tree(path: Path) -> str:
    """디렉터리 트리의 (상대경로, 내용) 전체에 대한 SHA-256 해시.

    정답 테스트(`tests/`)가 채점 시점까지 변경되지 않았는지 확인하는 용도.
    """
    h = hashlib.sha256()
    if not path.exists():
        return h.hexdigest()
    for p in sorted((q for q in path.rglob("*") if q.is_file()), key=lambda q: str(q.relative_to(path))):
        h.update(str(p.relative_to(path)).replace("\\", "/").encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def find_environment_tampering(original_workspace: Path, work: Path) -> list[str]:
    """에이전트가 pytest/파이썬 임포트 동작에 영향을 줄 수 있는 파일
    (conftest.py, sitecustomize.py, *.pth 등)을 새로 만들거나 고쳤는지 검사한다.

    완전한 샌드박스는 아니고 가장 흔한 변조 경로만 막는 휴리스틱이다 — 더
    강한 보장이 필요하면 컨테이너/샌드박스 실행으로 가야 한다.
    """
    findings = []
    for p in work.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(work)
        if rel.parts and rel.parts[0] == "tests":
            continue  # tests/는 hash_tree로 별도 검사
        if not (p.name in HOOK_FILENAMES or p.name.endswith(".pth")):
            continue
        original = original_workspace / rel
        new_content = p.read_bytes()
        old_content = original.read_bytes() if original.exists() else None
        if old_content != new_content:
            findings.append(f"{rel.as_posix()} ({'new' if old_content is None else 'modified'})")
    return findings


@dataclass
class DiffResult:
    """수정 전/후 디렉터리 비교 결과."""

    files_changed: int
    lines_changed: int
    text: str


def _diffable_files(before: Path, after: Path) -> list[Path]:
    after_files = {p.relative_to(after) for p in after.rglob("*") if p.is_file()}
    before_files = {p.relative_to(before) for p in before.rglob("*") if p.is_file()}
    rels = []
    for rel in after_files | before_files:
        if rel.parts and rel.parts[0] in IGNORED_TOP_LEVEL:
            continue
        if rel.name.startswith("_"):
            continue
        rels.append(rel)
    return sorted(rels, key=str)


def compute_diff(before: Path, after: Path) -> DiffResult:
    """두 디렉터리 트리를 비교해 변경 파일 수, 변경 라인 수, unified diff 텍스트를 반환한다."""
    files_changed = 0
    lines_changed = 0
    chunks: list[str] = []

    for rel in _diffable_files(before, after):
        b_path, a_path = before / rel, after / rel
        b = b_path.read_text(encoding="utf-8").splitlines(keepends=True) if b_path.exists() else []
        a = a_path.read_text(encoding="utf-8").splitlines(keepends=True) if a_path.exists() else []
        if b == a:
            continue
        diff_lines = list(difflib.unified_diff(b, a, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
        if not diff_lines:
            continue
        files_changed += 1
        lines_changed += sum(
            1 for line in diff_lines
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        )
        chunks.append("".join(diff_lines))

    return DiffResult(files_changed, lines_changed, "\n".join(chunks))

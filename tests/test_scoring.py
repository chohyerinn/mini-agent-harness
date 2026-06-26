"""변조 탐지·환경 격리·diff 측정 테스트.

평가 무결성의 핵심 방어선이라, "막아야 하는 것을 실제로 막는지"를 고정한다.
"""

from harness.scoring import (
    _sandboxed_env,
    compute_diff,
    find_environment_tampering,
    hash_tree,
    run_pytest,
)


def _two_trees(tmp_path):
    """동일한 내용의 base/work 디렉터리 쌍을 만든다."""
    base, work = tmp_path / "base", tmp_path / "work"
    for d in (base, work):
        d.mkdir()
        (d / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return base, work


# --- find_environment_tampering ------------------------------------------

def test_clean_workspace_no_findings(tmp_path):
    base, work = _two_trees(tmp_path)
    assert find_environment_tampering(base, work) == []


def test_detects_new_conftest(tmp_path):
    base, work = _two_trees(tmp_path)
    (work / "conftest.py").write_text("# evil\n", encoding="utf-8")
    findings = find_environment_tampering(base, work)
    assert any("conftest.py" in f and "new" in f for f in findings)


def test_detects_new_pyproject(tmp_path):
    # 이전에 누락돼 있던 갭: pyproject.toml도 pytest 설정 파일이다.
    base, work = _two_trees(tmp_path)
    (work / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    assert any("pyproject.toml" in f for f in find_environment_tampering(base, work))


def test_detects_pytest_module_shadow(tmp_path):
    # PYTHONPATH에 워크스페이스가 들어가므로 pytest.py로 모듈을 가릴 수 있다.
    base, work = _two_trees(tmp_path)
    (work / "pytest.py").write_text("# shadow\n", encoding="utf-8")
    assert any("pytest.py" in f for f in find_environment_tampering(base, work))


def test_detects_pth_file(tmp_path):
    base, work = _two_trees(tmp_path)
    (work / "evil.pth").write_text("import os\n", encoding="utf-8")
    assert any("evil.pth" in f for f in find_environment_tampering(base, work))


def test_detects_modified_existing_hook(tmp_path):
    base, work = tmp_path / "base", tmp_path / "work"
    for d in (base, work):
        d.mkdir()
        (d / "setup.cfg").write_text("[tool]\n", encoding="utf-8")
    (work / "setup.cfg").write_text("[tool]\nchanged = 1\n", encoding="utf-8")
    findings = find_environment_tampering(base, work)
    assert any("setup.cfg" in f and "modified" in f for f in findings)


def test_unchanged_existing_config_not_flagged(tmp_path):
    # 워크스페이스에 원래 있던, 바뀌지 않은 설정 파일은 오탐하지 않아야 한다.
    base, work = tmp_path / "base", tmp_path / "work"
    for d in (base, work):
        d.mkdir()
        (d / "pyproject.toml").write_text("[build-system]\n", encoding="utf-8")
    assert find_environment_tampering(base, work) == []


def test_changes_to_tests_dir_ignored_here(tmp_path):
    # tests/는 hash_tree로 별도 검사하므로 여기서는 무시한다.
    base, work = _two_trees(tmp_path)
    (work / "tests").mkdir()
    (work / "tests" / "conftest.py").write_text("# in tests\n", encoding="utf-8")
    assert find_environment_tampering(base, work) == []


# --- _sandboxed_env -------------------------------------------------------

def test_sandboxed_env_excludes_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-also-secret")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = _sandboxed_env(tmp_path)
    assert "ANTHROPIC_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert env.get("PATH") == "/usr/bin"


def test_sandboxed_env_fixes_hashseed_and_pythonpath(tmp_path):
    env = _sandboxed_env(tmp_path)
    assert env["PYTHONHASHSEED"] == "0"
    assert env["PYTHONPATH"] == str(tmp_path)


def test_docker_pytest_mode_uses_container_sandbox(monkeypatch, tmp_path):
    work = tmp_path / "work"
    (work / "tests").mkdir(parents=True)
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        (work / "_junit.xml").write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"/>', encoding="utf-8")
        class Proc:
            stdout = "docker ok\n"
            stderr = ""
        return Proc()

    monkeypatch.setenv("HARNESS_PYTEST_MODE", "docker")
    monkeypatch.setenv("HARNESS_DOCKER_IMAGE", "test-image")
    monkeypatch.setattr("subprocess.run", fake_run)

    passed, total, log = run_pytest(work)

    assert (passed, total) == (1, 1)
    assert "docker ok" in log
    assert captured["cmd"][:3] == ["docker", "run", "--rm"]
    assert "--network" in captured["cmd"]
    assert "none" in captured["cmd"]
    assert "test-image" in captured["cmd"]
    assert "/work/_junit.xml" in captured["cmd"]


# --- hash_tree / compute_diff --------------------------------------------

def test_hash_tree_stable_and_content_sensitive(tmp_path):
    d = tmp_path / "t"
    d.mkdir()
    (d / "a.py").write_text("x = 1\n", encoding="utf-8")
    h1 = hash_tree(d)
    assert h1 == hash_tree(d)  # 안정적
    (d / "a.py").write_text("x = 2\n", encoding="utf-8")
    assert hash_tree(d) != h1  # 내용이 바뀌면 해시도 바뀐다


def test_compute_diff_counts_changes(tmp_path):
    before, after = tmp_path / "b", tmp_path / "a"
    for d in (before, after):
        d.mkdir()
    (before / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (after / "mod.py").write_text("def f():\n    return 42\n", encoding="utf-8")
    diff = compute_diff(before, after)
    assert diff.files_changed == 1
    assert diff.lines_changed > 0
    assert "mod.py" in diff.text


def test_compute_diff_ignores_tests_and_underscore(tmp_path):
    before, after = tmp_path / "b", tmp_path / "a"
    for d in (before, after):
        (d / "tests").mkdir(parents=True)
    (after / "tests" / "test_x.py").write_text("assert True\n", encoding="utf-8")
    (after / "_solution").mkdir()
    (after / "_solution" / "s.py").write_text("y = 1\n", encoding="utf-8")
    diff = compute_diff(before, after)
    assert diff.files_changed == 0

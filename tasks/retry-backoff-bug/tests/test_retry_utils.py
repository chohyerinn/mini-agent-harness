import pytest

from retry_utils import call_with_retry


def make_flaky(fail_times):
    calls = {"count": 0}

    def fn():
        calls["count"] += 1
        if calls["count"] <= fail_times:
            raise ValueError(f"fail #{calls['count']}")
        return "ok"

    return fn, calls


def test_succeeds_after_retries():
    fn, calls = make_flaky(fail_times=2)
    result = call_with_retry(fn, attempts=3, base_delay=0)
    assert result == "ok"
    assert calls["count"] == 3


def test_succeeds_on_first_try():
    fn, calls = make_flaky(fail_times=0)
    result = call_with_retry(fn, attempts=3, base_delay=0)
    assert result == "ok"
    assert calls["count"] == 1


def test_uses_all_attempts_then_raises():
    fn, calls = make_flaky(fail_times=10)  # 항상 실패
    with pytest.raises(ValueError):
        call_with_retry(fn, attempts=3, base_delay=0)
    assert calls["count"] == 3


def test_default_attempts_is_three():
    fn, calls = make_flaky(fail_times=2)
    result = call_with_retry(fn, base_delay=0)
    assert result == "ok"
    assert calls["count"] == 3

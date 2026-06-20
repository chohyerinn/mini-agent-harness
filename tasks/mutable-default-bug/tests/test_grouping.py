from grouping import group_by_parity


def test_basic():
    assert group_by_parity([1, 2, 3, 4]) == {"even": [2, 4], "odd": [1, 3]}


def test_independent_calls_do_not_accumulate():
    # 가변 기본 인자가 공유되면 두 번째 호출에 첫 번째 결과가 남는다.
    first = group_by_parity([1, 2])
    second = group_by_parity([3, 4])
    assert first == {"even": [2], "odd": [1]}
    assert second == {"even": [4], "odd": [3]}


def test_explicit_bucket_still_works():
    target = {"even": [], "odd": []}
    out = group_by_parity([2, 5], target)
    assert out is target
    assert out == {"even": [2], "odd": [5]}

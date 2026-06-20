from seq_utils import dedupe


def test_preserves_order():
    assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]


def test_strings():
    assert dedupe(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]


def test_empty():
    assert dedupe([]) == []

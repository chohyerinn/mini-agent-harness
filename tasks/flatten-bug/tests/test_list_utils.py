from list_utils import flatten


def test_flat_input():
    assert flatten([1, 2, 3]) == [1, 2, 3]


def test_one_level():
    assert flatten([1, [2, 3], 4]) == [1, 2, 3, 4]


def test_deep_nesting():
    assert flatten([1, [2, [3, [4, [5]]]]]) == [1, 2, 3, 4, 5]


def test_multiple_nested_siblings():
    assert flatten([[1, [2, 3]], [4, [5, [6]]], 7]) == [1, 2, 3, 4, 5, 6, 7]


def test_empty():
    assert flatten([]) == []

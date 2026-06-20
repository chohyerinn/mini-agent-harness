from interval_utils import merge_intervals


def test_sorted_overlap():
    assert merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]]) == [[1, 6], [8, 10], [15, 18]]


def test_touching_intervals_merge():
    assert merge_intervals([[1, 4], [4, 5]]) == [[1, 5]]


def test_unsorted_input():
    assert merge_intervals([[8, 10], [1, 3], [2, 6], [15, 18]]) == [[1, 6], [8, 10], [15, 18]]


def test_unsorted_non_overlapping():
    assert merge_intervals([[5, 6], [1, 2]]) == [[1, 2], [5, 6]]


def test_single_interval():
    assert merge_intervals([[1, 2]]) == [[1, 2]]


def test_empty():
    assert merge_intervals([]) == []

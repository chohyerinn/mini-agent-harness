from search_utils import binary_search

ARR = [1, 3, 5, 7, 9]


def test_first_element():
    assert binary_search(ARR, 1) == 0


def test_last_element():
    assert binary_search(ARR, 9) == 4


def test_middle_element():
    assert binary_search(ARR, 5) == 2


def test_not_found():
    assert binary_search(ARR, 4) == -1


def test_single_element_found():
    assert binary_search([5], 5) == 0


def test_single_element_not_found():
    assert binary_search([5], 3) == -1


def test_empty():
    assert binary_search([], 1) == -1

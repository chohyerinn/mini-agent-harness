import pytest

from pagination import page_count


def test_exact_multiple():
    assert page_count(100, 10) == 10


def test_partial_last_page_rounds_up():
    assert page_count(11, 10) == 2
    assert page_count(1, 10) == 1
    assert page_count(95, 10) == 10


def test_empty():
    assert page_count(0, 10) == 0


def test_invalid_page_size():
    with pytest.raises(ValueError):
        page_count(10, 0)
    with pytest.raises(ValueError):
        page_count(10, -5)

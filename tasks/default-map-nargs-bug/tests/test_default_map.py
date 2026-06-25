from default_map import consume_default_map_value


def test_string_default_for_two_values_is_split():
    assert consume_default_map_value("3 4", nargs=2) == ["3", "4"]


def test_string_default_for_tuple_like_value_is_split():
    assert consume_default_map_value("hello world", nargs=2) == ["hello", "world"]


def test_single_value_string_is_not_split():
    assert consume_default_map_value("red", nargs=1) == "red"


def test_structured_values_pass_through():
    assert consume_default_map_value(("3", "4"), nargs=2) == ("3", "4")
    assert consume_default_map_value([5, 6], nargs=2) == [5, 6]


def test_custom_splitter_is_used():
    assert consume_default_map_value("a,b", nargs=2, splitter=lambda s: s.split(",")) == ["a", "b"]


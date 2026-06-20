from csv_utils import parse_csv_line


def test_plain_fields():
    assert parse_csv_line("a,b,c") == ["a", "b", "c"]


def test_quoted_field_with_comma():
    assert parse_csv_line('a,"b,c",d') == ["a", "b,c", "d"]


def test_quoted_field_at_start():
    assert parse_csv_line('"hello, world",foo') == ["hello, world", "foo"]


def test_no_quotes_no_comma():
    assert parse_csv_line("single") == ["single"]


def test_empty_line():
    assert parse_csv_line("") == []

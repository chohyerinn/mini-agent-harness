from text_utils import slugify


def test_basic():
    assert slugify("Hello World") == "hello-world"


def test_strip_symbols():
    assert slugify("Hello, World!") == "hello-world"


def test_collapse_and_trim():
    assert slugify("  Python   Rocks  ") == "python-rocks"


def test_keep_numbers():
    assert slugify("Top 10 Tips") == "top-10-tips"

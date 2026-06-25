from usage_format import format_usage


def test_empty_args_keeps_default_prefix_and_program():
    assert format_usage("cli") == "Usage: cli\n"


def test_empty_args_keeps_custom_prefix():
    assert format_usage("cli", prefix="Run: ") == "Run: cli\n"


def test_empty_args_has_no_trailing_space():
    assert format_usage("cli").splitlines()[0] == "Usage: cli"


def test_args_still_render_after_program():
    assert format_usage("cli", "[OPTIONS]") == "Usage: cli [OPTIONS]\n"


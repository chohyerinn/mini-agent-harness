import pytest

from label_format import format_command_help, format_option_help


@pytest.mark.parametrize("help_text", ["", None])
@pytest.mark.parametrize("deprecated", [True, "USE OTHER COMMAND"])
def test_command_empty_help_has_no_leading_space(help_text, deprecated):
    result = format_command_help(help_text, deprecated)
    assert result.startswith("(DEPRECATED")
    assert not result.startswith(" ")


@pytest.mark.parametrize("help_text", ["", None])
@pytest.mark.parametrize("deprecated", [True, "USE OTHER OPTION"])
def test_option_empty_help_has_no_leading_space(help_text, deprecated):
    result = format_option_help(help_text, deprecated)
    assert result.startswith("(DEPRECATED")
    assert not result.startswith(" ")


def test_nonempty_help_keeps_a_single_separator():
    assert format_command_help("Old command.", True) == "Old command. (DEPRECATED)"
    assert format_option_help("Old option.", "USE --new") == "Old option. (DEPRECATED: USE --new)"

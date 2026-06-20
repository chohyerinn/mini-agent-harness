def _deprecated_label(deprecated):
    if deprecated is True:
        return "(DEPRECATED)"
    return f"(DEPRECATED: {deprecated})"


def format_command_help(help_text, deprecated=False):
    text = help_text or ""
    if deprecated:
        label = _deprecated_label(deprecated)
        text = f"{text} {label}" if text else label
    return text


def format_option_help(help_text, deprecated=False):
    if deprecated:
        label = _deprecated_label(deprecated)
        return f"{help_text} {label}" if help_text else label
    return help_text

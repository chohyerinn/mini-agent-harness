def _deprecated_label(deprecated):
    if deprecated is True:
        return "(DEPRECATED)"
    return f"(DEPRECATED: {deprecated})"


def format_command_help(help_text, deprecated=False):
    text = help_text or ""
    if deprecated:
        # BUG: 빈 도움말에서도 label 앞에 공백이 남는다.
        text = f"{text} {_deprecated_label(deprecated)}"
    return text


def format_option_help(help_text, deprecated=False):
    if deprecated:
        label = _deprecated_label(deprecated)
        # BUG: 빈 문자열은 None이 아니어서 공백이 남는다.
        return f"{help_text} {label}" if help_text is not None else label
    return help_text

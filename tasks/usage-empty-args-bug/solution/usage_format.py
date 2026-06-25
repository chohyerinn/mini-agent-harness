def _wrap_text(text, initial_indent=""):
    # 실제 wrapping은 생략한 작은 재현 함수.
    if text == "":
        return "\n"
    return f"{initial_indent}{text}\n"


def format_usage(prog, args="", prefix=None, current_indent=0):
    prefix = "Usage: " if prefix is None else prefix
    usage_prefix = f"{' ' * current_indent}{prefix}{prog} "

    if not args:
        return f"{usage_prefix.rstrip(' ')}\n"

    return _wrap_text(args, initial_indent=usage_prefix)

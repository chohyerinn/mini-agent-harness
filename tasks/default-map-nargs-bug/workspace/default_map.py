def consume_default_map_value(value, nargs=1, splitter=None):
    if splitter is None:
        splitter = str.split

    # BUG: default_map에서 온 문자열도 다중 값 옵션이면 envvar처럼 split해야 한다.
    return value

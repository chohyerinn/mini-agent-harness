def consume_default_map_value(value, nargs=1, splitter=None):
    if splitter is None:
        splitter = str.split

    if isinstance(value, str) and nargs != 1:
        return splitter(value)

    return value

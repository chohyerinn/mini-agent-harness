def dedupe(items):
    # BUG: set은 순서를 보존하지 않는다
    return list(set(items))

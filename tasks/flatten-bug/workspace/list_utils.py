def flatten(nested):
    # BUG: 한 단계만 평탄화함 (예: [1, [2, [3, 4]]] -> [1, 2, [3, 4]])
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result

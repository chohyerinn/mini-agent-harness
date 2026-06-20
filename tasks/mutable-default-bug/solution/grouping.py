def group_by_parity(numbers, buckets=None):
    """numbers를 짝수/홀수로 나눠 buckets에 담아 돌려준다."""
    if buckets is None:
        buckets = {"even": [], "odd": []}
    for n in numbers:
        key = "even" if n % 2 == 0 else "odd"
        buckets[key].append(n)
    return buckets

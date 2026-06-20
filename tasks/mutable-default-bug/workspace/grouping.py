def group_by_parity(numbers, buckets={"even": [], "odd": []}):
    """numbers를 짝수/홀수로 나눠 buckets에 담아 돌려준다."""
    # BUG: 가변 기본 인자(buckets)가 함수 정의 시점에 한 번 만들어져 호출
    # 사이에 공유된다 — 호출할수록 이전 결과가 누적된다.
    for n in numbers:
        key = "even" if n % 2 == 0 else "odd"
        buckets[key].append(n)
    return buckets

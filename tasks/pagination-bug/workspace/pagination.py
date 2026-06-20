def page_count(total_items, page_size):
    """전체 항목 수와 페이지 크기로 필요한 페이지 수를 구한다."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    # BUG: 정수 나눗셈만 써서 나누어떨어지지 않는 마지막 부분 페이지를 누락한다.
    return total_items // page_size

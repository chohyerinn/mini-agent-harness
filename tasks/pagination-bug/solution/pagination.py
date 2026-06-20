def page_count(total_items, page_size):
    """전체 항목 수와 페이지 크기로 필요한 페이지 수를 구한다."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    if total_items <= 0:
        return 0
    return (total_items + page_size - 1) // page_size

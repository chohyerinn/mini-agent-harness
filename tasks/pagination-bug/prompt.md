# page_count 버그 수정

`pagination.py`의 `page_count(total_items, page_size)`는 전체 항목 수를
페이지 크기로 나눠 **필요한 페이지 수**를 돌려줘야 합니다. 하지만 지금은
정수 나눗셈만 사용해서 나누어떨어지지 않는 마지막 부분 페이지를 누락합니다.
예를 들어 항목 11개를 10개씩 나누면 2페이지가 필요한데 1을 반환합니다.

다음을 만족하도록 고치세요.

- 나누어떨어지지 않으면 올림: `page_count(11, 10) == 2`
- 정확히 나누어떨어지면 그대로: `page_count(100, 10) == 10`
- 항목이 0개면 0: `page_count(0, 10) == 0`
- `page_size`가 0 이하이면 `ValueError`

`pagination.py`만 수정하세요.

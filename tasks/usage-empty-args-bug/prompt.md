# 빈 args 사용법 출력 수정

`usage_format.py`의 `format_usage()`는 CLI 도움말 첫 줄을 만든다.
현재 구현은 `args`가 빈 문자열이면 prefix와 program name까지 사라져서 빈 줄만 반환한다.

- `args`가 비어 있으면 `Usage: prog`만 한 줄로 출력한다.
- `args`가 있으면 기존처럼 `Usage: prog args`를 출력한다.
- 사용자 지정 prefix도 유지한다.
- program name 뒤에 불필요한 trailing space가 남으면 안 된다.

이 과제는 Click PR #3434의 `HelpFormatter.write_usage` 빈 args 동작을 작은 독립 함수로 재현한 것이다.

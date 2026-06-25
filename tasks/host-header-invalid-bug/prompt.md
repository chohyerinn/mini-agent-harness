# Host header 누락 또는 invalid 문자 처리 수정

`host_utils.py`의 `get_host()`는 요청의 Host 값을 정리해서 반환한다.
현재 구현은 Host header가 없거나 invalid 문자가 있을 때 항상 `SecurityError`를 발생시킨다.

- Host header와 server 정보가 모두 없으면 빈 문자열을 반환한다.
- invalid 문자가 있는 Host도 trusted host 검사를 하지 않는 상황에서는 빈 문자열을 반환한다.
- trusted_hosts가 주어졌는데 host가 신뢰되지 않으면 기존처럼 `SecurityError`를 발생시킨다.
- 기본 포트 `:80`, `:443`은 scheme에 맞게 제거한다.

이 과제는 Werkzeug PR #3148의 `get_host` strictness 완화 동작을 작은 독립 함수로 재현한 것이다.

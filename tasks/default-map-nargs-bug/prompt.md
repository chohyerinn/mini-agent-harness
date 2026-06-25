# default_map 다중 값 문자열 split 수정

`default_map.py`의 `consume_default_map_value()`는 CLI 옵션의 기본값을 처리한다.
현재 구현은 `default_map`에서 온 문자열 값을 그대로 반환해서, `nargs > 1`인 옵션에서
`"3 4"`가 `["3", "4"]`로 나뉘지 않는다.

- `value`가 문자열이고 `nargs != 1`이면 `splitter(value)`로 나눈다.
- 이미 list/tuple로 들어온 값은 그대로 유지한다.
- `nargs == 1`인 문자열은 그대로 유지한다.

이 과제는 Click PR #3364의 default_map 다중 값 처리 동작을 작은 독립 함수로 재현한 것이다.

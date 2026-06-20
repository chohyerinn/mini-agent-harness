# 빈 도움말의 deprecated label 수정

`label_format.py`의 두 함수는 deprecated 항목의 도움말을 만든다. 도움말이 비어 있거나
`None`이면 `(DEPRECATED)` label 앞에 불필요한 공백이 붙는다.

- 도움말이 비어 있거나 없으면 label만 반환한다.
- 일반 도움말이 있으면 기존처럼 `도움말 + 공백 + label`을 반환한다.
- `deprecated=True`와 사용자 지정 사유 문자열을 모두 유지한다.

이 과제는 Click PR #3509의 동작을 작은 독립 함수로 재현한 것이다.

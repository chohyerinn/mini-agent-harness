# overlay enable_async 기본값 수정

`mini_jinja_env.py`의 `Environment.overlay()`는 기존 환경을 복사하면서 일부 옵션만
덮어쓰는 함수다. 현재 구현은 `enable_async` 기본값이 `False`라서, async 환경에서
`overlay()`만 호출해도 async 설정이 꺼진다.

- `overlay()`에 `enable_async`를 넘기지 않으면 기존 환경의 `is_async` 값을 유지한다.
- `overlay(enable_async=True)`는 async 환경을 만든다.
- `overlay(enable_async=False)`는 sync 환경을 만든다.

이 과제는 Jinja PR #2061의 `Environment.overlay(enable_async)` 기본값 수정 동작을 작은 독립 클래스로 재현한 것이다.

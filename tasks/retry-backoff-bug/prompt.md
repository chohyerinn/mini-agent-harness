# 과제: call_with_retry 재시도 횟수·예외 처리 버그 수정

`retry_utils.py`의 `call_with_retry(fn, attempts=3, base_delay=0.0)`는
`fn()`을 호출하고, 예외가 발생하면 지수적으로 늘어나는 지연(`base_delay * 2**시도횟수`)
후 재시도해야 합니다.

다음 두 가지를 만족하도록 수정하세요.

- 성공할 때까지 최대 `attempts`번 호출해야 합니다(현재는 `attempts - 1`번만 호출합니다).
- `attempts`번을 모두 실패하면 마지막 예외를 그대로 다시 발생(raise)시켜야 합니다.
  (현재는 예외를 삼키고 `None`을 반환합니다.)

테스트는 `tests/`에 있습니다. 테스트는 `base_delay=0`을 사용하므로 실제로
오래 기다리지는 않습니다. 모든 테스트를 통과시키세요.

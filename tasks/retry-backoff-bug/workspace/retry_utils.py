import time


def call_with_retry(fn, attempts=3, base_delay=0.0):
    last_exc = None
    for attempt in range(attempts - 1):
        # BUG: attempts번이 아니라 attempts-1번만 시도하고,
        # 모두 실패하면 예외를 삼키고 None을 반환해 버린다.
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            time.sleep(base_delay * (2 ** attempt))
    return None

# no_proxy 도메인 경계 매칭 수정

`proxy_rules.py`의 `should_bypass_proxy()`는 `no_proxy` 항목에 맞는 URL이면 `True`를
반환한다. 현재 단순 `endswith()` 비교 때문에 `localhost`가 `prelocalhost`에도 잘못
매칭된다.

- 정확히 같은 호스트는 매칭되어야 한다.
- `.example.com` 또는 `example.com`은 `api.example.com` 같은 하위 도메인과 매칭되어야 한다.
- 포트가 명시된 항목은 같은 호스트와 포트에만 매칭되어야 한다.
- 문자열 끝만 우연히 같은 다른 도메인은 매칭하면 안 된다.

이 과제는 Requests PR #7427의 `no_proxy` 도메인 경계 수정 동작을 작은 독립 함수로 재현한 것이다.

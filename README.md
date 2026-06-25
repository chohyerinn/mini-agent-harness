# mini-agent-harness

[![CI](https://github.com/chohyerinn/mini-agent-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/chohyerinn/mini-agent-harness/actions/workflows/ci.yml)

코딩 에이전트가 버그를 얼마나 안정적으로 고치는지 확인해 보기 위한 작은 평가 harness 입니다!

처음에는 “한 번 성공했는가”만 보면 될 줄 알았는데 LLM은 같은 입력에도 매번 결과가 달라집니다. 그래서 이 프로젝트는 단일 실행 결과보다 **반복 실행했을 때의 통과율, 분산, 실패 유형, 실행 시간**을 같이 봅니다.

지금 중심에 둔 모델은 **CLOVA Studio / HyperCLOVA X**입니다. 같은 CLOVA 모델을 단일 코딩 에이전트로도 돌리고, Planner-Coder-Reviewer 구조의 멀티에이전트로도 돌려 비교해 볼 수 있게 했습니다.

## 평가 방식

각 과제는 작은 Python 버그 수정 문제입니다.

```text
tasks/<task-id>/
  prompt.md       # 에이전트에게 줄 작업 설명
  workspace/      # 버그가 있는 코드
  tests/          # 채점용 테스트
  solution/       # mock 에이전트용 정답
  task.yaml       # 출처, 라이선스, 난이도 같은 메타데이터
```

실행할 때마다 하니스는 임시 작업 폴더를 만들고 에이전트에게는 `tests/`를 보여주지 않습니다. 에이전트가 코드를 수정한 뒤에만 테스트를 복사해서 채점합니다. `conftest.py`, `pytest.py`, `pyproject.toml` 같은 파일로 채점 환경을 건드리려는 변경은 변조로 처리합니다.

리포트에는 다음 값이 남습니다.

- solve rate
- 평균 점수와 표준편차
- pass@k
- bootstrap 95% CI 기반 A/B 비교
- 실행 시간
- token usage
- tokens/sec per solved run
- 실패 유형: planning error, implementation error, reviewer miss 등
- 응답 복구 여부: `<file>` 형식 대신 단일 Python 코드블록이 온 경우 안전하게 복구했는지 기록

## 로컬에서 감 잡기

API 키 없이도 mock 에이전트로 harness 흐름을 확인할 수 있습니다.

```bash
git clone https://github.com/chohyerinn/mini-agent-harness.git
cd mini-agent-harness

python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m harness.cli run --agent mock:solve --runs 1
python -m harness.cli run --agent mock:flaky:0.5 --runs 5
python -m harness.cli ab --a mock:solve --b mock:flaky:0.5 --runs 5
```

결과는 `reports/` 아래에 저장됩니다. 각 실행 폴더에는 `prompt.md`, `diff.patch`, `pytest.log`, `error.log`, `meta.json`이 남습니다.

## CLOVA로 돌리기

CLOVA Studio API 키가 있으면 실제 모델을 실행할 수 있습니다.

PowerShell 예시:

```powershell
$env:CLOVASTUDIO_API_KEY = "..."
$env:CLOVA_MODEL = "HCX-005"

python -m harness.cli run --agent clova --runs 3
python -m harness.cli run --agent multi:clova --runs 3
python -m harness.cli ab --a clova --b multi:clova --runs 5
```

기본 엔드포인트는 CLOVA Studio의 OpenAI-compatible API입니다.

```text
https://clovastudio.stream.ntruss.com/v1/openai
```

필요하면 환경변수로 바꿀 수 있습니다.

```powershell
$env:CLOVA_BASE_URL = "https://clovastudio.stream.ntruss.com/v1/openai"
$env:CLOVA_MAX_TOKENS = "4096"
$env:CLOVA_TEMPERATURE = "0"
$env:CLOVA_MAX_RETRIES = "3"
$env:CLOVA_RETRY_BASE_DELAY = "2"
```

`multi:clova`는 과제당 Planner/Coder/Reviewer 호출을 나눠 보내므로 단일 `clova`보다 API 호출 수가 많습니다. 429 rate limit이 나오면 기본적으로 잠깐 기다렸다가 재시도합니다.

연속 호출이 부담될 때는 실행 사이에 쉬는 시간을 둘 수 있습니다.

```powershell
python -m harness.cli ab --a clova --b multi:clova --runs 3 --sleep-between-runs 2
```

비용 추정은 프로젝트 안에 고정 가격표를 넣지 않았습니다. 과금 기준은 모델과 계정 설정에 따라 달라질 수 있어서, 기본값은 `0`으로 기록합니다. 직접 추정하고 싶으면 아래처럼 100만 토큰당 가격을 넣으면 됩니다.

```powershell
$env:CLOVA_INPUT_PRICE_PER_MTOK = "0.0"
$env:CLOVA_OUTPUT_PRICE_PER_MTOK = "0.0"
```

## 단일 에이전트와 멀티에이전트

`clova`는 한 번의 모델 호출로 코드를 수정합니다.

```bash
python -m harness.cli run --agent clova --runs 5
```

`multi:clova`는 같은 CLOVA 모델을 세 역할로 나눠 호출합니다.

```text
Planner  -> 수정 계획 작성
Coder    -> 실제 코드 수정
Reviewer -> 수정 결과 검토
```

```bash
python -m harness.cli run --agent multi:clova --runs 5
```

둘을 비교하면 “멀티에이전트 구조가 정말 더 나은가?”를 감으로만 보지 않고, 같은 과제와 같은 채점 기준에서 확인할 수 있습니다.

## 실험 메모

처음에는 Planner-Coder-Reviewer처럼 역할을 나누면 당연히 더 좋아질 것 같았습니다. 그런데 실제로는 호출 횟수도 늘고, 쉬운 문제에서는 오히려 불필요한 수정이 생길 수 있어서 한 번 숫자로 확인해 보고 싶었습니다.

2026-06-26에 `HCX-005`로 단일 에이전트와 Planner-Coder-Reviewer 구성을 비교했습니다. 15개 과제를 각각 3번씩 실행했고, 두 설정 모두 같은 테스트로 채점했습니다.

표본은 아직 작습니다. 15개 과제에 대해 3회씩만 반복한 결과이기 때문에, 아래 숫자는 일반적인 성능 결론이라기보다 이 작은 과제 집합에서 관찰한 경향으로 보는 것이 맞습니다.

| Agent | Solved runs | Total runs | Solve rate | Total tokens |
| --- | ---: | ---: | ---: | ---: |
| `clova:HCX-005` | 22 | 45 | 49% | 29,115 |
| `multi:clova:HCX-005` | 26 | 45 | 58% | 95,642 |

결과만 보면 멀티에이전트 쪽이 solved run은 조금 더 많았습니다. `csv-line-bug`, `dedupe-bug`, `flatten-bug`, `host-header-invalid-bug`, `no-proxy-boundary-bug`에서는 점수 차이가 신뢰구간 기준으로도 개선 쪽에 있었습니다. 특히 단일 에이전트가 거의 못 풀었던 `dedupe-bug`와 `no-proxy-boundary-bug`에서 차이가 컸습니다.

그렇다고 “멀티에이전트가 무조건 낫다”고 보기는 어렵습니다. `binary-search-bug`와 `default-map-nargs-bug`에서는 확정 회귀가 나왔습니다. 토큰 사용량도 약 3.3배 늘었고, solved run 하나당 걸린 시간도 `7.254s`에서 `23.629s`로 늘었습니다. 좋아진 부분은 있었지만 그만큼 비용과 지연시간도 같이 늘어난 셈입니다.

초기 실험에서 본 `slugify-bug` 실패도 기억해 둘 만했습니다. 단일 에이전트는 통과했지만, 멀티에이전트는 일부 실행에서 reviewer가 “문제 없어 보인다”고 넘긴 코드가 `"  Python   Rocks  "`를 `python-rocks`가 아니라 `python---rocks`로 만들었습니다. 역할을 나누면 검토 단계가 생기지만, 그 검토가 항상 edge case를 잡아 주는 것은 아니었습니다.

실행 중에는 `multi:clova`에서 429 rate limit도 만났습니다. 과제 하나를 풀 때 모델을 여러 번 부르기 때문에 생긴 문제였습니다. 그래서 CLOVA API 호출에 retry/backoff를 추가했습니다. 이 부분은 성능만 볼 게 아니라 실제 API 제한과 운영 비용도 같이 봐야 한다는 걸 확인한 부분이었습니다.

이 결과만으로 멀티에이전트가 항상 우수하다고 말할 수는 없습니다. 과제 수를 11개에서 15개로 늘리자 개선폭도 줄어들었습니다. 그래도 반환 타입, 재귀 처리, 도메인 경계처럼 edge case가 있는 과제에서는 역할을 나눈 구조가 단일 호출보다 안정적인 경우가 있었습니다.

## 현재 과제

현재 15개 과제가 들어 있습니다. 9개는 재현 가능한 synthetic bug이고, 6개는 실제 오픈소스 PR의 수정 내용을 작은 함수 단위로 줄여 만든 과제입니다.

이 프로젝트는 [SWE-bench](https://github.com/swe-bench/SWE-bench)처럼 실제 GitHub issue와 큰 코드베이스를 대상으로 하는 표준 벤치마크를 대체하려는 것은 아닙니다. 여기서는 작은 과제를 이용해 에이전트 반복 실행, 테스트 격리, A/B 비교, 실패 유형 기록 같은 평가 흐름을 직접 구현해 보는 데 초점을 두었습니다.

| Task | Origin | Provenance |
| --- | --- | --- |
| `default-map-nargs-bug` | `default_map` 문자열 값이 다중 값 옵션에서 split되지 않음 | [pallets/click#3364](https://github.com/pallets/click/pull/3364), commit `a014796`, BSD-3-Clause |
| `deprecated-label-bug` | deprecated label 공백 처리 버그 | [pallets/click#3509](https://github.com/pallets/click/pull/3509), commit `82f377c`, BSD-3-Clause |
| `host-header-invalid-bug` | Host header 누락/invalid 문자 처리 완화 | [pallets/werkzeug#3148](https://github.com/pallets/werkzeug/pull/3148), commit `deab88f`, BSD-3-Clause |
| `no-proxy-boundary-bug` | `no_proxy` 도메인 경계 매칭 버그 | [psf/requests#7427](https://github.com/psf/requests/pull/7427), commit `52220f6`, Apache-2.0 |
| `overlay-enable-async-bug` | overlay 환경이 기존 async 설정을 덮어씀 | [pallets/jinja#2061](https://github.com/pallets/jinja/pull/2061), commit `e45bc74`, BSD-3-Clause |
| `usage-empty-args-bug` | 빈 args 사용법 출력에서 prefix와 program name이 사라짐 | [pallets/click#3434](https://github.com/pallets/click/pull/3434), commit `0551bf5`, BSD-3-Clause |

## 파일 구조

```text
harness/
  runner.py       # 작업 폴더 준비, 테스트 격리, 아티팩트 저장
  scoring.py      # pytest 실행, diff 생성, 변조 탐지
  benchmark.py    # 반복 실행과 A/B 비교
  stats.py        # pass@k, bootstrap CI
  trace.py        # token/cost/time/failure summary
  agents/
    clova.py      # CLOVA 단일/멀티 에이전트
    mock.py       # API 없이 쓰는 테스트용 에이전트
tasks/            # 평가 과제
tests/            # 하니스 자체 테스트
```

## 검증

```bash
pytest tests -q
```

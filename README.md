# mini-agent-harness

코딩 에이전트가 버그를 얼마나 안정적으로 고치는지 확인하기 위한 작은 평가 하니스입니다.

처음에는 “한 번 성공했는가”만 보면 될 줄 알았는데, LLM은 같은 입력에도 매번 결과가 달라집니다. 그래서 이 프로젝트는 단일 실행 결과보다 **반복 실행했을 때의 통과율, 분산, 실패 유형, 실행 시간**을 같이 봅니다.

지금 중심에 둔 모델은 **CLOVA Studio / HyperCLOVA X**입니다. 같은 CLOVA 모델을 단일 코딩 에이전트로도 돌리고, Planner-Coder-Reviewer 구조의 멀티에이전트로도 돌려 비교할 수 있게 했습니다.

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

실행할 때마다 하니스는 임시 작업 폴더를 만들고, 에이전트에게는 `tests/`를 보여주지 않습니다. 에이전트가 코드를 수정한 뒤에만 테스트를 복사해서 채점합니다. `conftest.py`, `pytest.py`, `pyproject.toml` 같은 파일로 채점 환경을 건드리려는 변경은 변조로 처리합니다.

리포트에는 다음 값이 남습니다.

- solve rate
- 평균 점수와 표준편차
- pass@k
- bootstrap 95% CI 기반 A/B 비교
- 실행 시간
- token usage
- 실패 유형: planning error, implementation error, reviewer miss 등

## 로컬에서 감 잡기

API 키 없이도 mock 에이전트로 하니스 흐름을 확인할 수 있습니다.

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

둘을 비교하면 “멀티에이전트 구조가 정말 더 나은가?”를 감이 아니라 같은 과제, 같은 채점 기준, 반복 실행 결과로 볼 수 있습니다.

## 실험 메모

2026-06-26에 `HCX-005`로 단일 에이전트와 Planner-Coder-Reviewer 구성을 비교했습니다. 각 과제를 3번씩 반복 실행했고, 같은 11개 과제와 같은 채점 기준을 사용했습니다.

| Agent | Solved runs | Total runs | Solve rate | Total tokens |
| --- | ---: | ---: | ---: | ---: |
| `clova:HCX-005` | 19 | 33 | 58% | 20,855 |
| `multi:clova:HCX-005` | 25 | 33 | 76% | 68,963 |

멀티에이전트는 `dedupe-bug`, `flatten-bug`, `no-proxy-boundary-bug`, `csv-line-bug`에서 확정 개선을 보였습니다. 특히 단일 에이전트가 0점에 가까웠던 `dedupe-bug`와 `no-proxy-boundary-bug`에서 개선 폭이 컸습니다.

다만 좋은 결과만 있었던 것은 아닙니다. `binary-search-bug`, `pagination-bug`처럼 단일 에이전트도 거의 만점에 가까웠던 쉬운 과제에서는 멀티에이전트가 아주 작은 점수 회귀를 보였습니다. 또한 멀티에이전트는 호출 수가 많아 토큰 사용량이 약 3.3배 증가했습니다.

이 실험 뒤에는 `multi:clova` 실행 중 429 rate limit이 발생했습니다. 그래서 CLOVA API 호출에 retry/backoff를 추가했습니다. 이 부분은 성능뿐 아니라 실제 운영 비용과 API 제한도 같이 봐야 한다는 점을 확인한 사례였습니다.

## 현재 과제

현재 11개 과제가 들어 있습니다. 대부분은 재현 가능한 synthetic bug이고, 일부는 실제 오픈소스 PR의 수정 내용을 작은 함수 단위로 줄여 만든 과제입니다.

| Task | Origin | Provenance |
| --- | --- | --- |
| `deprecated-label-bug` | deprecated label 공백 처리 버그 | [pallets/click#3509](https://github.com/pallets/click/pull/3509), commit `82f377c`, BSD-3-Clause |
| `no-proxy-boundary-bug` | `no_proxy` 도메인 경계 매칭 버그 | [psf/requests#7427](https://github.com/psf/requests/pull/7427), commit `52220f6`, Apache-2.0 |

## 개발자가 보는 파일

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

GitHub Actions에서는 실제 CLOVA API를 호출하지 않습니다. 비용과 비밀키 문제를 피하기 위해 mock 에이전트와 단위 테스트만 실행합니다. 실제 모델 평가는 로컬에서 API 키를 설정한 뒤 실행합니다.

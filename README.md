# mini-agent-harness

코딩 에이전트를 바꾸거나 프롬프트를 수정했을 때, 결과가 정말 나아졌는지 확인하기 위한 작은 평가 도구입니다.

같은 버그 수정 과제를 여러 번 실행하고 테스트 결과, 수정 diff, 실행 시간, 점수 분포를 남깁니다. 한 번 잘 풀었다는 결과보다 **반복했을 때도 믿을 만한지**를 보는 데 초점을 둡니다.

## 이 프로젝트를 만든 이유

에이전트 평가는 쉽게 “이번 모델이 더 좋아 보인다”는 인상으로 끝납니다. 이 프로젝트는 그 인상을 확인 가능한 결과로 바꾸려 합니다.

- 과제마다 독립된 임시 작업 폴더를 사용합니다.
- 같은 에이전트를 여러 번 실행해 solve rate, 평균 점수, 표준편차, pass@k를 계산합니다.
- A/B 비교에서는 평균 차이만 보고 회귀라고 단정하지 않습니다. bootstrap 95% CI가 0보다 완전히 낮을 때만 확정 회귀로 표시합니다.
- 각 실행의 prompt, diff, pytest 로그, 오류, 환경 정보를 저장합니다.

## 직접 실행해 보기

```bash
git clone https://github.com/chohyerinn/mini-agent-harness.git
cd mini-agent-harness

python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# 기본 동작 확인
python -m harness.cli run --agent mock:solve

# 반복 실행으로 분산 확인
python -m harness.cli run --agent mock:flaky:0.5 --runs 5

# 두 에이전트 비교
python -m harness.cli ab --a mock:solve --b mock:flaky:0.5 --runs 5
```

실제 Claude adapter를 실행하려면 API 키를 설정합니다.

```powershell
$env:ANTHROPIC_API_KEY = "..."
python -m harness.cli run --agent claude --runs 5

# Planner/Coder/Reviewer 멀티에이전트와 단일 Claude 비교
python -m harness.cli ab --a claude --b multi:claude-opus-4-8 --runs 5
```

결과는 `reports/`에 저장됩니다. 실행별 폴더에는 `prompt.md`, `diff.patch`, `pytest.log`, `error.log`, `meta.json`이 들어 있습니다.

## 결과를 읽는 법

- **solve rate**: 모든 테스트를 통과한 실행의 비율
- **평균 점수 ± 표준편차**: 테스트 통과율을 기본으로 하고 큰 수정에는 작은 감점을 적용한 값
- **pass@k**: k번 시도했을 때 한 번 이상 성공할 확률의 추정값
- **확정 회귀**: B-A 평균 점수 차이의 bootstrap 95% CI가 전부 0보다 낮은 경우
- **회귀 후보**: 평균은 낮지만 CI가 0을 걸쳐 표본만으로 단정할 수 없는 경우

`mock:solve`, `mock:noop`, `mock:flaky`는 외부 API 없이 runner와 통계를 확인하기 위한 테스트용 에이전트입니다. 실제 모델 성능을 주장하는 결과는 아닙니다.

## 과제 구성

```text
tasks/<task-id>/
  task.yaml       # 난이도와 출처 메타데이터
  prompt.md       # 에이전트에게 전달할 작업 설명
  workspace/      # 버그가 있는 코드
  tests/          # 채점용 테스트
  solution/       # mock:solve용 참고 정답
```

현재 11개 과제가 있습니다. 9개는 재현 가능한 synthetic 버그이고, 2개는 실제 오픈소스 버그 수정 PR의 동작을 작은 독립 함수로 재현했습니다.

| Task | Origin | Provenance |
| --- | --- | --- |
| `deprecated-label-bug` | 빈 도움말의 deprecated label 앞 공백 | [pallets/click#3509](https://github.com/pallets/click/pull/3509), commit `82f377c`, BSD-3-Clause |
| `no-proxy-boundary-bug` | `no_proxy`의 잘못된 도메인 끝 문자열 매칭 | [psf/requests#7427](https://github.com/psf/requests/pull/7427), commit `52220f6`, Apache-2.0 |

각 `task.yaml`은 `source`, `source_ref`, `source_commit`, `license`를 기록합니다. 그래서 나중에 과제가 어디서 왔고 어떤 변경을 재현하는지 추적할 수 있습니다.

## 평가가 지키는 선

에이전트가 테스트 답을 미리 보거나 채점 환경을 바꾸는 것을 줄이기 위해 다음을 적용했습니다.

- 에이전트가 실행되는 동안 `tests/`는 작업 폴더에 없습니다.
- 채점 직전에 원본 테스트를 새로 복사하고, 실행 전후 해시를 비교합니다.
- `conftest.py`, `pyproject.toml`, `pytest.py` 같은 pytest/import 훅 파일의 추가·변경을 감지하면 해당 실행은 0점입니다.
- pytest subprocess에는 API 키를 넘기지 않고 필요한 환경변수만 전달합니다.

이것은 평가 조작을 줄이는 방어선이지 완전한 보안 샌드박스는 아닙니다. 신뢰하지 않는 agent나 과제는 Docker 같은 별도 격리 환경에서 실행해야 합니다.

## 코드 구조

```text
harness/
  runner.py       # 작업 폴더 준비, 테스트 격리, 아티팩트 저장
  scoring.py      # pytest 실행, diff와 변조 탐지
  benchmark.py    # 반복 실행 집계와 A/B 판정
  stats.py        # pass@k와 bootstrap CI
  agents/         # mock, Claude adapter
tasks/            # 평가 과제
tests/            # harness 자체 단위 테스트
```

## 검증

```bash
pytest tests -q
```

GitHub Actions는 harness 단위 테스트, `mock:solve` 스모크 테스트, 반복 A/B 실행을 확인합니다. 실제 LLM 호출은 비용과 비결정성 때문에 CI에서 실행하지 않습니다.

## trace와 실패 유형

각 실행의 `meta.json`에는 점수뿐 아니라 측정 근거도 함께 남습니다.

- `agent_trace`: 단일 호출 또는 Planner/Coder/Reviewer 단계별 시간, 토큰 수, 예상 비용
- `token_usage`: 전체 input/output/total token 합계
- `estimated_cost_usd`: 모델 가격표 기반 추정 비용
- `stage_durations_s`: agent 실행, tamper scan, pytest, diff 등 harness 단계별 시간
- `failure_type`: `planning_error`, `implementation_error`, `reviewer_miss`, `partial_implementation`, `agent_error`, `tamper`, `solved`

이 값들은 A/B 리포트에도 집계됩니다. 그래서 단순히 “멀티에이전트가 더 좋다/나쁘다”가 아니라, 어느 단계에서 시간이 늘었는지, 비용이 얼마나 증가했는지, 실패가 계획·구현·리뷰 중 어디에 가까운지 같이 볼 수 있습니다.

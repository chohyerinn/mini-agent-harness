# mini-agent-harness

![CI](https://github.com/chohyerinn/mini-agent-harness/actions/workflows/ci.yml/badge.svg)

코딩 에이전트가 버그 수정 과제를 얼마나 잘, 그리고 얼마나 **일관되게** 푸는지
확인하기 위한 작은 평가 도구입니다.

모델이나 프롬프트를 바꾸고 나면 보통 "전보다 나아진 것 같은데?"에서 끝나는
경우가 많습니다. 한 번 실행해서 통과했다고 해서 그 에이전트가 그 과제를
안정적으로 푸는 것도 아니고, 실패했다고 해서 항상 실패하는 것도 아닙니다.
이 도구는 같은 과제·에이전트 조합을 여러 번 반복 실행해 **solve rate, 평균
점수, 표준편차, pass@k**를 측정하고, 실행마다 무엇을 했는지(diff, 테스트
로그, 에러)를 남겨서 "왜" 실패했는지까지 추적할 수 있게 만드는 것을
목표로 합니다.

## 하는 일

- 과제별로 격리된 임시 작업 폴더를 만들고 에이전트에게 버그 수정을 맡깁니다.
- 수정이 끝나면 pytest를 실행해 채점합니다.
- `--runs N`으로 같은 조합을 N번 반복 실행하고, solve rate / 평균 점수 /
  표준편차 / 최소·최대 점수 / pass@k를 계산합니다.
- 실행마다 prompt, 코드 diff, pytest 로그, 에러 로그, 실행 시간을
  `reports/runs/`에 남깁니다.
- 두 에이전트(또는 두 설정)를 `ab`로 비교하면 과제별 평균±표준편차와
  부트스트랩 신뢰구간 기반 회귀 판정을 보여 줍니다.
- 에이전트 실행이 끝나기 전까지 정답 테스트를 작업 폴더에 노출하지 않고,
  pytest 서브프로세스 환경 변수를 화이트리스트로 제한해 비밀값 유출과
  테스트 변조를 막습니다.

점수는 테스트 통과율을 기본으로 하고 과도한 수정량에 소폭 감점을 적용하는
방식입니다(`harness/models.py`의 `RunResult.score`). 점수 하나로 에이전트의
품질을 단정하기보다는, 같은 조건에서 반복 비교할 때 참고하는 값으로
사용합니다.

## 빠른 시작

```bash
git clone https://github.com/chohyerinn/mini-agent-harness.git
cd mini-agent-harness

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt

# 기본 mock 에이전트를 1회 실행
python -m harness.cli run --agent mock:solve

# 같은 조합을 5번 반복 실행 — solve rate/평균/표준편차/pass@k까지 계산
python -m harness.cli run --agent mock:solve --runs 5

# 두 에이전트를 각 5회씩 실행해 회귀 비교
python -m harness.cli ab --a mock:solve --b mock:flaky:0.5 --runs 5

# 실제 Claude 에이전트로 평가 (ANTHROPIC_API_KEY 필요, anthropic 패키지 설치 필요)
export ANTHROPIC_API_KEY=sk-...
python -m harness.cli run --agent claude --runs 5
python -m harness.cli ab --a claude --b mock:noop --runs 5   # 실제 에이전트 vs 무작업 베이스라인
```

`--tasks`, `--out`은 서브커맨드(`run`/`ab`) **앞에** 와야 합니다(전역 옵션):

```bash
python -m harness.cli --out my-reports run --agent mock:solve --runs 5
```

결과는 `reports/`에 Markdown과 JSON으로, 실행별 아티팩트는
`reports/runs/`에 저장됩니다.

## pass@k의 정의

**pass@k = "같은 과제에 k번 시도하면 적어도 한 번은 성공할 확률"** 입니다.

과제·에이전트 조합을 매번 다시 k번씩 실행해서 이 확률을 직접 추정하면
비용이 크기 때문에, 이 도구는 Chen et al. (2021, Codex/HumanEval 논문)의
불편추정량(unbiased estimator)을 사용합니다. 과제 하나를 `n`번 독립
실행해서 `c`번 성공했다면,

```
pass@k = 1 - C(n-c, k) / C(n, k)
```

즉 "n번 중 실패한 (n-c)번에서만 k개를 뽑았을 때 전부 실패할 확률"을 1에서
뺀 값입니다. 구현은 `harness/stats.py::pass_at_k`에 있고, 수치 안정성을 위해
조합수 대신 곱 형태로 계산합니다.

**예시** — `csv-line-bug`를 `mock:flaky:0.5`로 5번 돌렸더니 1번만 성공했다면
(`n=5, c=1`):

- `pass@1 = c/n = 1/5 = 20%` (한 번 시도했을 때 성공할 확률)
- `pass@3 = 1 - C(4,3)/C(5,3) = 1 - 4/10 = 60%`
- `pass@5 = 100%` (남은 실패 횟수 `n-c=4`가 `k=5`보다 작으므로 항상 1)

리포트의 `pass@k`는 과제별로 이렇게 추정한 값을 전체 과제에 대해 평균한
것입니다(HumanEval과 동일한 집계 방식). `run`/`ab` 명령은 기본적으로
`k = 1, 5, runs` 중 `runs` 이하인 값들을 보여 줍니다.

## 실행 단위 아티팩트

`--runs`와 무관하게 **모든 실행**은 아티팩트를 남깁니다. 회귀가 발생했을 때
"몇 점 떨어졌다"에서 멈추지 않고 "어떤 수정 때문에 떨어졌는지"를 바로 볼 수
있게 하기 위함입니다.

```
reports/runs/<timestamp>_<agent>/<task-id>/run-<n>/
  prompt.md     # 이번 실행에서 에이전트에게 전달된 프롬프트
  diff.patch    # 수정 전/후 unified diff (빈 파일이면 "시도조차 안 함"을 의미)
  pytest.log    # pytest stdout+stderr 전체
  error.log     # 에이전트 실행 중 발생한 예외 (없으면 빈 파일)
  meta.json     # passed/total/score/files_changed/lines_changed/duration_s/
                # prompt_hash/agent_fingerprint/tamper_detected/tamper_reason/
                # environment(harness 커밋 SHA·파이썬·플랫폼·의존성 버전)
```

`prompt_hash`는 이번 실행에 실제로 쓰인 prompt의 SHA-256 앞 12자(같은
prompt가 실행마다 그대로 쓰였는지 확인용)이고, `agent_fingerprint`는
에이전트가 스스로 보고하는 실행 설정입니다(Claude 어댑터는 `model`,
`max_tokens`, `thinking`, anthropic SDK 버전을 기록 — `harness/agents/claude.py`,
`harness/agents/mock.py` 참고). `environment`는 결과를 나중에 재현·대조할 수
있도록 **harness 커밋 SHA(워킹트리가 더러우면 `-dirty`), 파이썬·플랫폼·핵심
의존성(pytest/PyYAML/anthropic) 버전**을 함께 남긴 것입니다
(`harness/runner.py::runtime_metadata`). 같은 점수라도 "어떤 harness 버전·
환경에서 나온 결과인지"를 구분할 수 있습니다.

`ab` 명령은 두 에이전트의 아티팩트를 같은 타임스탬프 아래
`.../<a-agent>/...`, `.../<b-agent>/...`로 나란히 남깁니다.

## 평가 무결성: 테스트 격리와 변조 탐지

에이전트가 정답 테스트를 미리 읽고 답을 맞추거나, 테스트 파일 자체를 고쳐서
통과시켜 버리면 점수를 신뢰할 수 없습니다. `harness/runner.py`는 다음
순서로 이를 막습니다.

1. **정답 테스트는 에이전트 실행이 끝난 뒤에만 작업 폴더에 넣습니다.**
   `agent.run()`이 도는 동안 `tests/`는 작업 폴더에 존재하지 않습니다.
2. **채점 직전, 에이전트가 무엇을 만들어 놨든 `tests/`를 통째로 지우고
   과제 원본에서 새로 복사합니다.** 에이전트가 가짜 통과 테스트를 미리
   `tests/`에 심어 놔도 그대로 덮어써집니다.
3. **pytest 실행 전후로 `tests/`의 SHA-256 해시를 비교합니다.** pytest
   실행 중에(예: 악의적인 플러그인을 통해) 테스트 파일이 바뀌면 감지합니다.
4. **`conftest.py`, `pytest.ini`, `pyproject.toml`, `setup.cfg`,
   `sitecustomize.py`, `*.pth` 등 pytest나 파이썬 임포트 동작에 전역으로
   끼어들 수 있는 파일이 새로 생기거나 바뀌었는지 검사합니다**
   (`harness/scoring.py::find_environment_tampering`). 채점 서브프로세스의
   PYTHONPATH에 워크스페이스가 들어가므로, `pytest.py`/`pluggy.py`처럼
   기존 모듈을 같은 이름으로 가리는(shadowing) 파일도 함께 막습니다. 원래
   워크스페이스에 있던, 바뀌지 않은 설정 파일은 오탐하지 않습니다(before/after
   내용 비교).
5. **pytest 서브프로세스에는 전체 `os.environ`을 물려주지 않고, 화이트리스트
   (`PATH`, `PYTHONPATH` 등 실행에 꼭 필요한 키)만 넘깁니다**
   (`harness/scoring.py::_sandboxed_env`). 에이전트를 호출하는 데 쓰인
   `ANTHROPIC_API_KEY` 같은 값이 과제 코드(테스트로 실행되는 워크스페이스)
   를 통해 새어 나가지 않게 하기 위함입니다.
6. **변조가 감지되면(`RunResult.tamper_detected`) pytest 결과와 무관하게
   점수를 0점으로 강제합니다.** 일단 테스트 무결성이 깨졌다고 판단되면 그
   실행의 pytest 출력 자체를 신뢰할 수 없기 때문입니다. 사유는
   `error.log`/`meta.json`의 `tamper_reason`에 남습니다.

**한계:** 이건 화이트리스트/해시 비교에 기반한 휴리스틱이며, 실제 OS
수준 샌드박스나 컨테이너 격리가 아닙니다. 파일시스템·네트워크 접근을 막진
않으므로, 신뢰할 수 없는 에이전트나 과제 코드를 돌릴 때는 여전히 컨테이너
(Docker 등) 안에서 실행하는 것을 권장합니다 — "남은 작업"에 기록해 뒀습니다.

## 회귀 판정 방법: candidate vs 확정

`--runs`로 반복 실행해도, **A의 평균 점수가 B보다 높다는 것만으로 회귀라고
단정하지 않습니다.** 표본이 5개 정도면 에이전트 실력 차이가 아니라 순전히
운으로도 평균이 갈릴 수 있기 때문입니다. `ab` 명령은 과제별로 다음을
계산합니다(`harness/stats.py::bootstrap_mean_diff_ci`,
`harness/benchmark.py::_verdict`).

1. `mean(B) - mean(A)`에 대한 95% percentile bootstrap 신뢰구간을 구합니다
   (각 쪽에서 복원추출로 2,000번 리샘플링).
2. 신뢰구간이 **0 미만에 완전히 들어가면** → `regression`(확정된 회귀).
3. 신뢰구간이 **0을 걸치면** → 평균은 떨어졌어도 `regression_candidate`
   (회귀처럼 보이지만 표본으로는 확신할 수 없음)로만 표시합니다.
4. 양쪽 표본이 2개 미만이면(`--runs 1`) 신뢰구간을 추정할 수 없으므로
   `insufficient_data`로 표시합니다 — `--runs 1`로 받은 결과를 "회귀"라고
   말하지 않습니다.

리포트(`reports/ab-*.md`)는 "확정된 회귀"와 "회귀 후보"를 별도 절로
나눠서 보여 줍니다. 아래는 실제로 관찰된 예시입니다(`mock:solve` 대비
`mock:flaky:0.5`, 각 5회 — 자세한 수치는 다음 절 참고): `binary-search-bug`
는 평균이 99.94 → 88.54로 떨어졌지만(Δ -11.4) 95% CI가 `[-22.81, +0.0]`로
0을 걸쳐서 **회귀 후보로만** 표시되고, `dedupe-bug`는 99.82 → 33.33,
CI `[-66.49, -66.49]`로 0을 전혀 포함하지 않아 **확정된 회귀**로 표시됩니다.
평균 델타만 보는 도구였다면 둘 다 똑같이 "회귀"라고 했을 것입니다.

## 과제 구성

```text
tasks/<task-id>/
  task.yaml       # id, category, difficulty, source(synthetic|pr) 등 메타데이터
  prompt.md       # 에이전트에게 전달할 설명
  workspace/      # 버그가 있는 코드
  tests/          # 채점용 테스트
  solution/       # mock:solve가 사용할 참고 정답(선택)
```

과제를 실행할 때는 `workspace/`를 임시 폴더로 복사해서 사용합니다. 원본
과제 파일은 수정하지 않습니다.

현재 9개 과제가 들어 있으며, 모두 재현 가능하도록 직접 작성한 합성
(synthetic) 버그입니다. 실제 PR 이력을 무리하게 긁어모으는 대신, 난이도별로
작고 검증된 버그를 먼저 갖추는 쪽을 택했습니다. `task.yaml`에는
`source: synthetic | pr` 필드가 있어서, 나중에 실제 PR 기반 과제를 추가할 때
원본 PR/이슈 링크(`source_ref`), 기준 커밋 SHA(`source_commit`), 라이선스
(`license`)를 같은 스키마로 기록할 수 있습니다.

| Task | 난이도 | 무엇이 버그인가 |
|---|---|---|
| `slugify-bug` | easy | 소문자 변환·기호 제거·하이픈 정리가 빠짐 |
| `dedupe-bug` | easy | `set()`을 써서 입력 순서를 보존하지 못함 |
| `flatten-bug` | easy | 한 단계만 평탄화하고 깊은 중첩을 처리 못함 |
| `binary-search-bug` | easy | `low < high`라 마지막 후보(`low == high`)를 확인 안 함 |
| `merge-intervals-bug` | medium | 입력이 정렬돼 있다고 가정해 정렬 안 된 입력에서 병합 실패 |
| `csv-line-bug` | medium | 인용부호 안의 쉼표까지 구분자로 잘못 처리 |
| `retry-backoff-bug` | hard | `attempts-1`번만 시도하고 마지막 예외를 삼켜 `None` 반환 |
| `pagination-bug` | medium | `//` 정수 나눗셈만 써서 마지막 부분 페이지를 누락(올림 빠짐) |
| `mutable-default-bug` | medium | 가변 기본 인자가 호출 간 공유돼 결과가 누적됨 |

## 실험: mock 에이전트 3종을 각 5회 실행

아직 실제 LLM 에이전트를 붙이지 않았으므로, 아래 결과는 **harness의 통계
계산이 의도대로 동작하는지**를 mock 에이전트로 보여 주는 것이며 실제
에이전트의 성능에 대한 주장은 아닙니다. `mock:solve`/`mock:noop`은
결정론적(매번 같은 결과)이고, `mock:flaky:0.5`는 매 실행마다 50% 확률로만
정답을 적용하는 비결정론적 에이전트입니다 — 실제 LLM처럼 같은 과제를
여러 번 돌려도 결과가 갈리는 상황을 재현하기 위해 추가했습니다
(`harness/agents/mock.py::FlakyMockAgent`).

7개 과제 × 5회 실행, `python -m harness.cli run --agent <agent> --runs 5`
(아래 수치는 `pagination-bug`/`mutable-default-bug`를 추가하기 전, 처음 7개
과제 기준입니다):

| 에이전트 | solve rate | 평균 점수 | 평균 표준편차 | pass@1 | pass@5 |
|---|---|---|---|---|---|
| `mock:solve` | 100% | 99.87 | 0.0 | 100% | 100% |
| `mock:noop` | 0% | 42.35 | 0.0 | 0% | 0% |
| `mock:flaky:0.5` | 40% | 66.22 | 25.73 | 40% | 86% |

`mock:flaky:0.5`의 과제별 결과(표준편차가 큰 순):

| Task | 해결 | solve rate | 평균 점수 | 표준편차 | 최소 | 최대 |
|---|---|---|---|---|---|---|
| slugify-bug | 3/5 | 60% | 59.89 | 54.67 | 0.0 | 99.82 |
| retry-backoff-bug | 3/5 | 60% | 69.89 | 40.98 | 25.0 | 99.82 |
| csv-line-bug | 2/5 | 40% | 63.95 | 32.8 | 40.0 | 99.88 |
| merge-intervals-bug | 2/5 | 40% | 79.95 | 18.19 | 66.67 | 99.88 |
| flatten-bug | 1/5 | 20% | 67.99 | 17.86 | 60.0 | 99.94 |
| binary-search-bug | 3/5 | 60% | 88.54 | 15.62 | 71.43 | 99.94 |
| dedupe-bug | 0/5 | 0% | 33.33 | 0.0 | 33.33 | 33.33 |

관찰한 것:

- **결정론적 에이전트는 표준편차가 항상 0**입니다. `mock:flaky`만 표준편차가
  의미를 갖고, 한 번의 실행만으로는 그 변동을 알 수 없습니다 — 이게
  `--runs`를 만든 이유입니다.
- **`slugify-bug`가 표준편차 54.67로 가장 컸습니다.** 성공(99.82점)과
  완전 실패(0.0점) 사이를 오갔기 때문입니다. 반면 `binary-search-bug`는
  실패해도 기존 테스트 일부가 통과해 71.43점 밑으로는 떨어지지 않아 변동이
  작았습니다. → **같은 평균 점수라도 어떤 과제는 "거의 항상 그 정도"이고
  어떤 과제는 "운이 좋으면 만점, 나쁘면 0점"인지가 다릅니다.** solve rate나
  평균만 보면 이 차이가 보이지 않습니다.
- **`dedupe-bug`는 5번 모두 0/5로, 가장 안정적으로 보이는 결과(표준편차 0)
  였지만 사실은 "5번 다 시도 자체를 안 한" 결과였습니다.** 저장된
  아티팩트(`reports/runs/.../dedupe-bug/run-*/diff.patch`)를 열어보면 5번
  모두 **diff가 0바이트**였습니다. 점수나 solve rate만 봤다면 "이 과제를
  꾸준히 실패한다"와 "이 과제를 한 번도 시도하지 않았다"를 구분할 수
  없었을 것이고, 바로 이 차이를 보여주기 위해 실행 단위 아티팩트
  (prompt/diff/로그)를 남기기로 했습니다.

같은 데이터를 `ab`(`mock:solve` 대비 `mock:flaky:0.5`, 각 5회)로 보면
**평균만 봤을 때와 통계적 판정이 갈리는 사례가 바로 나타납니다.**

| Task | A 평균 | B 평균 | Δ | 95% CI(B-A) | 판정 |
|---|---|---|---|---|---|
| binary-search-bug | 99.94 | 88.54 | -11.4 | `[-22.81, +0.0]` | 🔶 회귀 후보 |
| retry-backoff-bug | 99.82 | 69.89 | -29.93 | `[-59.86, +0.0]` | 🔶 회귀 후보 |
| slugify-bug | 99.82 | 59.89 | -39.93 | `[-79.86, +0.0]` | 🔶 회귀 후보 |
| csv-line-bug | 99.88 | 63.95 | -35.93 | `[-59.88, -11.98]` | 🔻 회귀(확정) |
| dedupe-bug | 99.82 | 33.33 | -66.49 | `[-66.49, -66.49]` | 🔻 회귀(확정) |
| flatten-bug | 99.94 | 67.99 | -31.95 | `[-39.94, -15.98]` | 🔻 회귀(확정) |
| merge-intervals-bug | 99.88 | 79.95 | -19.93 | `[-33.21, -6.64]` | 🔻 회귀(확정) |

7개 과제 모두 평균 점수는 떨어졌지만(Δ가 전부 음수), **3개는 신뢰구간이
0을 걸쳐서 "회귀 후보"로만 표시됩니다.** 예를 들어 `binary-search-bug`는
Δ -11.4로 결정론적 베이스라인(`mock:solve`)보다 또렷이 나빠 보이지만,
5회라는 표본으로는 "진짜로 더 못 푼다"와 "이번엔 운이 나빴다"를 통계적으로
구분할 수 없습니다. 평균 차이만 보는 도구라면 이 7개를 전부 "회귀"라고
보고했을 것이고, 실제로 이전 버전의 이 프로젝트가 그렇게 했습니다. 실제
리포트는 `reports/ab-<날짜>-mock_solve-vs-mock_flaky.md`에서 확인할 수
있습니다.

## 실제 에이전트 붙이기

`harness/agents/claude.py`에 실제로 동작하는 Claude(Anthropic) 어댑터가
들어 있습니다(`claude` / `claude:<model>`, 기본 `claude-opus-4-8`).
`ANTHROPIC_API_KEY`를 설정하고 `pip install anthropic`을 하면
`--agent claude`로 바로 실 에이전트를 평가할 수 있습니다. 동작 방식은
workdir의 `*.py` 소스를 프롬프트와 함께 모델에 전달하고, 모델이
`<file path="...">...</file>` 블록으로 돌려준 전체 파일 내용을 다시
workdir에 덮어쓰는 단순한 구조입니다.

다른 LLM을 붙이려면 `harness/agents/`에 아래 형태의 어댑터를 만들고
`build_agent()`(`harness/agents/__init__.py`)에 분기를 추가하면 됩니다.

```python
from pathlib import Path

class MyAgent:
    name = "my-agent"

    def run(self, workdir: Path, prompt: str) -> None:
        # prompt를 읽고 workdir 안의 파일을 직접 수정
        ...
```

`mock:solve`/`mock:noop`/`mock:flaky[:p]`는 실제 LLM이 아닙니다. 외부 API
없이 실행 흐름, 반복 실행 통계, A/B 비교가 제대로 동작하는지 확인하기 위한
테스트용 에이전트입니다.

## CI

`.github/workflows/ci.yml`은 (1) harness 자체의 단위 테스트(`pytest tests` —
pass@k·부트스트랩 CI 같은 통계 함수, 변조 탐지, 테스트 격리), (2) `mock:solve`가
모든 과제를 풀고(`solve_rate == 1.0`) `mock:noop`이 아무 과제도 풀지
않는지(`solve_rate == 0.0`) 확인하는 스모크 테스트, (3) `--runs`를 사용한 `ab`
실행이 에러 없이 끝나는지를 확인합니다. 실제 LLM 에이전트의 점수를 CI에서
매번 재현하는 것은 비용·비결정성 때문에 다루지 않습니다.

harness 단위 테스트는 로컬에서 `pytest tests`로 바로 돌릴 수 있습니다
(`tests/test_stats.py`, `test_scoring.py`, `test_runner.py`, `test_benchmark.py`).

## 남은 작업

- **컨테이너/샌드박스 격리.** 지금의 변조 탐지(파일 해시·환경 변수
  화이트리스트)는 휴리스틱이고, 진짜 OS 수준 격리는 아닙니다. 신뢰할 수
  없는 에이전트를 돌리려면 Docker 등 컨테이너 안에서 실행하는 게 다음 단계.
- **모델 응답 원문·토큰 수·비용 기록.** 실행 환경 메타데이터(harness 커밋
  SHA·파이썬·의존성 버전)와 에이전트 설정(`model`/`max_tokens`/`thinking`/SDK
  버전)은 이제 `meta.json`에 남습니다. 다만 Claude의 **실제 응답 텍스트와 API
  사용량(토큰 수·비용)**, 오류 유형은 아직 저장하지 않아, "왜 이 diff가
  나왔는지"를 완전히 재현하려면 응답 원문 저장(선택적)이 더 필요합니다.
- **Claude 어댑터의 입력·비용 상한.** 지금은 워크스페이스의 모든 `*.py`를
  한 번에 보내고 `max_tokens=16000`으로 호출합니다. 수정 허용 파일 제한,
  파일 수/바이트 수 상한, timeout/재시도/비용 상한이 필요합니다.
- **실제 PR 기반 과제 추가.** 지금 9개는 전부 합성(synthetic) 버그입니다.
  `pagination-bug`/`mutable-default-bug`는 실무에서 흔한 버그 패턴(올림 누락,
  가변 기본 인자)을 본떴지만 여전히 직접 작성한 것입니다. `task.yaml`의
  `source: pr` 스키마(원본 PR 링크/기준 커밋 SHA/라이선스)가 준비돼 있으니,
  2~3개만이라도 실제 오픈소스 PR에서 라이선스를 확인해 가져오면 좋습니다.
- Claude 외 다른 LLM 에이전트 어댑터 추가 (OpenAI 등)
- 여러 리포트를 모아 추이를 볼 수 있는 간단한 화면

## 주의

이 도구는 로컬에서 임의의 Python 코드와 테스트를 실행합니다. 정답 테스트
숨김/변조 탐지, pytest 환경 변수 화이트리스트 같은 안전장치가 있지만
(["평가 무결성" 절](#평가-무결성-테스트-격리와-변조-탐지) 참고) 이것들은
휴리스틱이고 컨테이너/샌드박스를 대체하지 않습니다. 신뢰할 수 있는 과제와
에이전트만 사용해야 하고, 정말로 신뢰할 수 없는 코드를 평가해야 한다면
컨테이너 격리를 먼저 추가하세요.

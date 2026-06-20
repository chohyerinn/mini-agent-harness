# mini-agent-harness

코딩 에이전트가 버그 수정 과제를 얼마나 잘 푸는지 확인하려고 만든 작은 평가 도구입니다.

모델이나 프롬프트를 바꾸고 나면 보통 “전보다 나아진 것 같은데?”에서 끝나는 경우가 많습니다. 이 프로젝트에서는 같은 과제를 같은 방식으로 돌려 보고, 테스트 결과와 수정량, 실행 시간만 간단히 기록합니다. 복잡한 벤치마크보다 에이전트를 비교해 보는 출발점에 가깝습니다.

## 하는 일

- 과제별로 임시 작업 폴더를 만든 뒤 에이전트에게 버그 수정을 맡깁니다.
- 수정이 끝나면 Pytest를 실행합니다.
- 테스트 통과 수, 수정한 파일·줄 수, 걸린 시간을 저장합니다.
- 두 에이전트를 실행하면 과제별 점수 차이와 회귀 여부를 보여 줍니다.

현재 점수는 테스트 통과율에서 수정량에 따른 작은 감점을 적용하는 방식입니다. 점수 하나로 에이전트의 품질을 단정하기보다는, 결과를 비교할 때 참고할 값으로 사용합니다.

## 실행

```bash
git clone https://github.com/chohyerinn/mini-agent-harness.git
cd mini-agent-harness

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt

# 기본 mock 에이전트 실행
python -m harness.cli run --agent mock:solve

# A/B 비교
python -m harness.cli ab --a mock:solve --b mock:noop

# 실제 Claude 에이전트로 평가 (ANTHROPIC_API_KEY 필요)
export ANTHROPIC_API_KEY=sk-...
python -m harness.cli run --agent claude
python -m harness.cli ab --a claude --b mock:noop   # 실제 에이전트 vs 무작업 베이스라인
```

결과는 `reports/`에 Markdown과 JSON 파일로 저장됩니다.

## 과제 구조

```text
tasks/<task-id>/
  task.yaml       # 과제 정보
  prompt.md       # 에이전트에게 전달할 설명
  workspace/      # 버그가 있는 코드
  tests/          # 채점용 테스트
  solution/       # mock:solve가 사용할 참고 정답(선택)
```

지금은 아래 두 과제가 들어 있습니다.

- `slugify-bug`: 공백과 대소문자 처리가 잘못된 slug 함수 수정
- `dedupe-bug`: 입력 순서를 유지하지 못하는 중복 제거 함수 수정

과제를 실행할 때는 `workspace/`를 임시 폴더로 복사해서 사용합니다. 원래 과제 파일은 수정하지 않습니다.

## 실제 에이전트 붙이기

`harness/agents/`에 아래 형태의 어댑터를 만들고 `build_agent()`에 등록하면 됩니다.

```python
from pathlib import Path

class MyAgent:
    name = "my-agent"

    def run(self, workdir: Path, prompt: str) -> None:
        # prompt를 읽고 workdir 안의 파일을 수정
        ...
```

기본으로 들어 있는 `mock:solve`, `mock:noop`는 실제 LLM이 아닙니다. 외부 API 없이 실행 흐름과 A/B 비교가 제대로 동작하는지 확인하기 위한 테스트용 에이전트입니다.

실제 LLM 어댑터로는 `claude`(`harness/agents/claude.py`)가 들어 있습니다. `ANTHROPIC_API_KEY`를 설정하면 `--agent claude`로 평가할 수 있고, CLOVA 등 다른 LLM도 같은 방식으로 추가할 수 있습니다.

## 남은 작업

- 실제 PR 이력에서 과제를 만들기
- 결과 추이를 볼 수 있는 간단한 화면 추가하기
- 에이전트 로그를 저장해 회귀 원인까지 확인하기

## 주의

이 도구는 로컬에서 Python 코드와 테스트를 실행합니다. 신뢰할 수 있는 과제와 에이전트만 사용해야 합니다.

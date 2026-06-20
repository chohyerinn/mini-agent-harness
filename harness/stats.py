"""반복 실행 결과에 대한 통계: 평균/표준편차, pass@k, A/B 유의성 검정."""

from __future__ import annotations

import math
import random


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: list[float]) -> float:
    """표본 표준편차(n-1). 표본이 1개 이하면 분산을 정의할 수 없어 0.0을 반환."""
    n = len(values)
    if n < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))


def pass_at_k(n: int, c: int, k: int) -> float:
    """pass@k: 같은 과제를 n번 독립 시행해 c번 성공했을 때,
    그중 무작위로 k번을 뽑으면 적어도 한 번은 성공할 확률의 불편추정량.

    Chen et al., "Evaluating Large Language Models Trained on Code" (2021)의
    추정식을 그대로 사용한다.

        pass@k = 1 - C(n-c, k) / C(n, k)

    n번 중 k번을 뽑는 조합 중 "k번 모두 실패"인 조합의 비율을 1에서 뺀 값이며,
    n번을 전부 매번 다시 실행하지 않고도 적은 표본으로 pass@k를 추정할 수 있게 해준다.
    실패 횟수(n - c)가 k보다 작으면 항상 성공이 포함되므로 1.0이다.
    """
    if k <= 0 or n <= 0:
        return 0.0
    if k > n:
        k = n
    if n - c < k:
        return 1.0
    # prod_{i=0}^{k-1} (n-c-i) / (n-i)  ==  C(n-c, k) / C(n, k)
    prod = 1.0
    for i in range(k):
        prod *= (n - c - i) / (n - i)
    return 1.0 - prod


def bootstrap_mean_diff_ci(
    a: list[float], b: list[float], n_boot: int = 2000, alpha: float = 0.05, seed: int = 12345,
) -> tuple[float, float]:
    """mean(b) - mean(a)에 대한 percentile bootstrap (1-alpha) 신뢰구간.

    A/B의 평균 점수가 다르다는 것만으로는 "표본이 5개라 우연히 갈렸다"와
    "꾸준히 차이가 난다"를 구분할 수 없다. a, b 각각에서 복원추출로 같은
    크기의 표본을 `n_boot`번 뽑아 평균차이의 분포를 만들고, 그 분포의
    alpha/2 ~ 1-alpha/2 분위수를 신뢰구간으로 쓴다(Koehn 2004 식 페어드
    부트스트랩과 동일한 아이디어). 신뢰구간이 0을 포함하지 않으면 그
    방향으로 통계적으로 뒷받침된 차이라고 본다.

    표본이 같은 데이터라면 항상 같은 신뢰구간이 나오도록 리샘플링 시드를
    고정한다(재현성). a 또는 b의 표본이 2개 미만이면 분산을 추정할 수 없으니
    퇴화 구간(점추정값 그대로)을 반환한다 — 호출하는 쪽에서 `n < 2`일 때는
    "표본 부족"으로 별도 처리해야 한다.
    """
    if len(a) < 2 or len(b) < 2:
        d = round(mean(b) - mean(a), 2) if a and b else 0.0
        return (d, d)
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_boot):
        sample_a = rng.choices(a, k=len(a))
        sample_b = rng.choices(b, k=len(b))
        diffs.append(mean(sample_b) - mean(sample_a))
    diffs.sort()
    lo_idx = max(0, int((alpha / 2) * n_boot))
    hi_idx = min(n_boot - 1, int((1 - alpha / 2) * n_boot))
    return (round(diffs[lo_idx], 2), round(diffs[hi_idx], 2))

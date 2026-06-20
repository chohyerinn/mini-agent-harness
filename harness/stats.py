"""반복 실행 결과에 대한 통계: 평균/표준편차와 pass@k."""

from __future__ import annotations

import math


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

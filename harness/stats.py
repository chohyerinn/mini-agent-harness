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


def paired_bootstrap_diff_ci(
    pairs: list[tuple[float, float]],
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 12345,
) -> tuple[float, float]:
    """같은 과제 집합에서 두 설정을 비교할 때의 *페어드* 부트스트랩 CI.

    `bootstrap_mean_diff_ci`는 a, b를 각각 독립으로 리샘플링한다(한 과제
    안에서 두 설정이 서로 다른 무작위 실행이라 적절). 하지만 suite 전체의
    solve rate를 비교할 때는 두 설정이 *같은 과제 집합*을 풀므로, 과제 단위로
    짝을 유지한 채 리샘플링해야 한다. 어떤 과제가 둘 다에게 쉽거나 어렵다는
    상관(난이도 공변)을 무시하면 분산을 과대평가해 실제 차이를 못 잡는다.

    pairs = [(a_i, b_i), ...]  과제 i에서의 두 설정 지표(예: 과제별 solve rate).
    같은 인덱스 묶음으로 복원추출해 mean(b)-mean(a)의 분포를 만들고,
    그 (1-alpha) percentile 구간을 돌려준다. 시드 고정으로 재현 가능.
    과제가 2개 미만이면 분산을 추정할 수 없어 점추정값을 그대로 돌려준다.
    """
    n = len(pairs)
    if n < 2:
        d = round(pairs[0][1] - pairs[0][0], 4) if n == 1 else 0.0
        return (d, d)
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        a_sum = sum(pairs[i][0] for i in idx)
        b_sum = sum(pairs[i][1] for i in idx)
        diffs.append((b_sum - a_sum) / n)
    diffs.sort()
    lo_idx = max(0, int((alpha / 2) * n_boot))
    hi_idx = min(n_boot - 1, int((1 - alpha / 2) * n_boot))
    return (round(diffs[lo_idx], 4), round(diffs[hi_idx], 4))


def mcnemar_test(only_a: int, only_b: int) -> tuple[float, float]:
    """McNemar 검정: 같은 항목을 두 설정이 푼 이진 결과(성공/실패)를 비교한다.

    같은 과제(여기서는 같은 (과제, run) 쌍)를 두 설정이 모두 풀므로, 두 설정의
    성공률 차이를 볼 때 표준 도구는 독립표본 검정이 아니라 *짝지은* McNemar
    검정이다. 둘 다 성공/둘 다 실패한 일치쌍은 차이 정보를 주지 않아 버리고,
    한쪽만 성공한 불일치쌍만 본다.

        only_a: A만 성공(B는 실패)한 쌍의 수
        only_b: B만 성공(A는 실패)한 쌍의 수

    불일치쌍이 적을 때(<25) 카이제곱 근사는 부정확하므로 정확 이항검정(양측)을
    쓰고, 충분히 많으면 연속성 보정 카이제곱을 쓴다. chi2(자유도 1)의
    꼬리확률은 P(chi2_1 > x) = erfc(sqrt(x/2)) 이므로 scipy 없이 계산한다.

    (statistic, p_value)를 돌려준다. 불일치쌍이 0이면 판단 근거가 없어 (0.0, 1.0).
    """
    n = only_a + only_b
    if n == 0:
        return (0.0, 1.0)
    statistic = max(0.0, (abs(only_a - only_b) - 1) ** 2 / n)  # 연속성 보정
    if n < 25:
        k = min(only_a, only_b)
        tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
        p = min(1.0, 2.0 * tail)
    else:
        p = math.erfc(math.sqrt(statistic / 2))
    return (round(statistic, 4), round(p, 4))

"""통계 함수(pass@k, 표준편차, 부트스트랩 CI) known-answer 테스트.

이 함수들은 평가 결과 해석의 근거다 — pass@k가 틀리면 "k번 시도하면 풀 확률"이
틀리고, 부트스트랩 CI가 틀리면 "회귀 후보 vs 확정 회귀" 구분이 통째로 틀어진다.
모두 순수 함수(시드 고정 = 결정론적)라 손으로 검산한 값으로 못박는다.
"""

import math

from harness.stats import (
    bootstrap_mean_diff_ci,
    mcnemar_test,
    mean,
    paired_bootstrap_diff_ci,
    pass_at_k,
    stdev,
)


# --- mean / stdev ---------------------------------------------------------

def test_mean_basic():
    assert mean([1.0, 2.0, 3.0]) == 2.0


def test_mean_empty_is_zero():
    assert mean([]) == 0.0


def test_stdev_single_sample_is_zero():
    # 표본 1개로는 분산을 정의할 수 없다.
    assert stdev([5.0]) == 0.0


def test_stdev_empty_is_zero():
    assert stdev([]) == 0.0


def test_stdev_uses_sample_formula_not_population():
    # 두 점 {2, 4}의 표본 표준편차(n-1)는 |4-2|/sqrt(2) = sqrt(2) ≈ 1.414.
    # 모표준편차(n)였다면 1.0이 나온다 — n-1을 쓰는지 명시적으로 검증한다.
    assert math.isclose(stdev([2.0, 4.0]), math.sqrt(2.0))
    assert not math.isclose(stdev([2.0, 4.0]), 1.0)


def test_stdev_identical_values_is_zero():
    assert stdev([7.0, 7.0, 7.0, 7.0]) == 0.0


# --- pass@k (Chen et al. 2021 추정식) -------------------------------------

def test_pass_at_k_never_solved():
    assert pass_at_k(5, 0, 1) == 0.0
    assert pass_at_k(5, 0, 5) == 0.0


def test_pass_at_k_always_solved():
    assert pass_at_k(5, 5, 1) == 1.0
    assert pass_at_k(5, 5, 3) == 1.0


def test_pass_at_1_equals_c_over_n():
    assert math.isclose(pass_at_k(5, 2, 1), 0.4)
    assert math.isclose(pass_at_k(2, 1, 1), 0.5)


def test_pass_at_k_readme_example():
    # README 예시: n=5, c=1 → pass@3 = 1 - C(4,3)/C(5,3) = 1 - 4/10 = 0.6
    assert math.isclose(pass_at_k(5, 1, 3), 0.6)


def test_pass_at_k_humaneval_style():
    # n=200, c=100 → pass@1 = 0.5
    assert math.isclose(pass_at_k(200, 100, 1), 0.5)


def test_pass_at_k_failures_fewer_than_k_is_one():
    # 실패 횟수(n-c=4)가 k=5보다 작으면 어떤 k개를 뽑아도 성공이 포함된다.
    assert pass_at_k(5, 1, 5) == 1.0


def test_pass_at_k_clamps_k_greater_than_n():
    # k>n이면 k=n으로 클램프; n-c=2 < 5 → 1.0
    assert pass_at_k(5, 3, 10) == 1.0


def test_pass_at_k_guards():
    assert pass_at_k(0, 0, 1) == 0.0   # n<=0
    assert pass_at_k(5, 0, 0) == 0.0   # k<=0


def test_pass_at_k_monotonic_in_k():
    # 같은 (n, c)에서 k가 커지면 "적어도 한 번 성공"할 확률은 줄지 않는다.
    vals = [pass_at_k(10, 3, k) for k in range(1, 11)]
    assert all(a <= b + 1e-12 for a, b in zip(vals, vals[1:]))


# --- bootstrap 신뢰구간 ---------------------------------------------------

def test_bootstrap_is_deterministic():
    # 시드를 고정하므로 같은 입력은 항상 같은 구간을 낸다(재현성).
    a = [10.0, 20.0, 30.0, 15.0, 25.0]
    b = [40.0, 50.0, 45.0, 55.0, 42.0]
    assert bootstrap_mean_diff_ci(a, b) == bootstrap_mean_diff_ci(a, b)


def test_bootstrap_clear_difference_excludes_zero():
    # b가 a보다 확실히 높으면 CI가 0을 포함하지 않고 양수쪽으로 떨어진다 → 확정.
    a = [10.0, 11.0, 9.0, 10.0, 12.0]
    b = [90.0, 88.0, 92.0, 91.0, 89.0]
    lo, hi = bootstrap_mean_diff_ci(a, b)
    assert lo > 0 and hi > 0


def test_bootstrap_overlap_includes_zero():
    # 사실상 같은 분포면 CI가 0을 걸친다 → 후보로만 봐야 한다.
    a = [50.0, 52.0, 48.0, 51.0, 49.0]
    b = [50.0, 49.0, 51.0, 52.0, 48.0]
    lo, hi = bootstrap_mean_diff_ci(a, b)
    assert lo <= 0.0 <= hi


def test_bootstrap_degenerate_small_sample():
    # 한쪽 표본이 2개 미만이면 분산 추정 불가 → 점추정값 그대로(퇴화 구간).
    lo, hi = bootstrap_mean_diff_ci([100.0], [0.0])
    assert lo == hi == -100.0


def test_bootstrap_empty_inputs():
    assert bootstrap_mean_diff_ci([], []) == (0.0, 0.0)


# --- 페어드 부트스트랩 (suite 차원 solve rate) ----------------------------

def test_paired_bootstrap_is_deterministic():
    pairs = [(0.2, 0.6), (0.4, 0.4), (0.0, 0.8), (0.6, 0.6), (0.2, 1.0)]
    assert paired_bootstrap_diff_ci(pairs) == paired_bootstrap_diff_ci(pairs)


def test_paired_bootstrap_clear_difference_excludes_zero():
    # 모든 과제에서 b가 a보다 꾸준히 높으면 CI가 0 위로 떨어진다.
    pairs = [(0.0, 1.0)] * 8
    lo, hi = paired_bootstrap_diff_ci(pairs)
    assert lo > 0 and hi > 0


def test_paired_bootstrap_no_difference_includes_zero():
    # 과제마다 방향이 엇갈리면(평균차 0) CI가 0을 걸친다 → 유의하지 않음.
    pairs = [(0.2, 0.8), (0.8, 0.2), (0.5, 0.5), (0.3, 0.7), (0.7, 0.3)]
    lo, hi = paired_bootstrap_diff_ci(pairs)
    assert lo <= 0.0 <= hi


def test_paired_bootstrap_degenerate_small_sample():
    assert paired_bootstrap_diff_ci([(0.2, 0.9)]) == (0.7, 0.7)
    assert paired_bootstrap_diff_ci([]) == (0.0, 0.0)


# --- McNemar 검정 ---------------------------------------------------------

def test_mcnemar_no_discordant_pairs():
    # 불일치쌍이 없으면 차이를 판단할 근거가 없다 → p=1.
    assert mcnemar_test(0, 0) == (0.0, 1.0)


def test_mcnemar_symmetric_is_not_significant():
    # A만 성공 = B만 성공이면 차이 증거가 없다 → p가 크다.
    stat, p = mcnemar_test(5, 5)
    assert p > 0.5


def test_mcnemar_all_one_direction_small_sample_exact():
    # B만 8번 성공, A만 0번 → 정확 이항검정 양측 p = 2 * 0.5^8 = 0.0078125.
    stat, p = mcnemar_test(0, 8)
    assert math.isclose(p, 0.0078, abs_tol=1e-3)
    assert p < 0.05


def test_mcnemar_large_sample_uses_chi_square():
    # 불일치쌍이 25 이상이면 연속성 보정 카이제곱 근사를 쓴다.
    # only_a=5, only_b=25 → χ² = (|5-25|-1)^2/30 = 361/30 ≈ 12.03 → 매우 유의.
    stat, p = mcnemar_test(5, 25)
    assert math.isclose(stat, 12.0333, abs_tol=1e-3)
    assert p < 0.001


def test_mcnemar_p_is_symmetric_in_arguments():
    # 두 인자를 바꿔도 같은 통계량/p (방향만 다르고 유의성은 동일).
    assert mcnemar_test(3, 12) == mcnemar_test(12, 3)

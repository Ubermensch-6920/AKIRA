"""Tests for the hand-built NumPy MYGA engine.

Steps 1-6 are pinned to small hand calculations. Step 7 and the final
reconciliation compare against the gaspatchio benchmark engine.
"""

from __future__ import annotations

import numpy as np
import pytest

from actuarial_model.assumptions.sets import MortalityConfig
from actuarial_model.engine.handbuilt import myga as hb
from actuarial_model.engine.projection import CASH_FLOW_COLUMNS, COUNT_COLUMNS
from actuarial_model.engine.projections import myga as benchmark
from tests.factories import VAL_DATE
from tests.test_engine.test_myga_projection import _config, _portfolio

# ── Step 1 — Time ────────────────────────────────────────────────────────────


def test_step1_duration_and_policy_year():
    duration, year = hb.duration_and_policy_year(np.array([0, 18]), 14)
    assert duration.shape == year.shape == (2, 14)
    np.testing.assert_array_equal(duration[0, :3], [0, 1, 2])
    np.testing.assert_array_equal(duration[1, :3], [18, 19, 20])
    assert year[0, 11] == 1 and year[0, 12] == 2  # month 12 starts policy year 2
    assert year[1, 0] == 2 and year[1, 6] == 3  # 24 months → year 3


def test_step1_attained_age():
    duration = np.array([[0, 11, 12, 25], [0, 12, 24, 36]])
    ages = hb.attained_age(np.array([60, 129]), duration, max_age=130)
    np.testing.assert_array_equal(ages, [[60, 60, 61, 62], [129, 130, 130, 130]])


# ── Step 2 — Rate conversions ────────────────────────────────────────────────


def test_step2_annual_to_monthly_decrement():
    monthly = hb.annual_to_monthly_decrement(np.array([0.0, 0.12, 1.0]))
    np.testing.assert_allclose(monthly, [0.0, 1 - 0.88 ** (1 / 12), 1.0])
    # 12 months of survival reproduce the annual rate
    assert (1 - hb.annual_to_monthly_decrement(0.05)) ** 12 == pytest.approx(0.95)


def test_step2_monthly_credit_rate():
    monthly = hb.monthly_credit_rate(np.array([0.03, 0.0]))
    np.testing.assert_allclose((1 + monthly) ** 12, [1.03, 1.0])
    assert monthly[0] < hb.annual_to_monthly_decrement(0.03)  # the old over-credit


# ── Step 3 — Policy-year lookup ──────────────────────────────────────────────


def test_step3_rate_by_policy_year():
    years = np.array([[1, 2, 3, 4, 5, 6], [3, 3, 3, 4, 4, 4]])
    rates = hb.rate_by_policy_year(years, 0.02, {3: 0.20, 5: 0.40})
    np.testing.assert_allclose(
        rates, [[0.02, 0.02, 0.20, 0.02, 0.40, 0.02], [0.20, 0.20, 0.20, 0.02, 0.02, 0.02]]
    )
    np.testing.assert_allclose(hb.rate_by_policy_year(years, 0.05, {}), 0.05)


# ── Step 4 — Mortality ───────────────────────────────────────────────────────


def test_step4_adjusted_annual_qx():
    mort = MortalityConfig(mortality_multiplier=1.1, g2_scale_multiplier=0.5, flat_improvement_rate=0.01)
    base = np.array([[0.01, 0.02]])
    g2 = np.array([[0.02, 0.01]])
    years_g2 = np.array([13.0, 14.0])
    years_issue = np.array([[0.0, 1.0]])
    qx = hb.adjusted_annual_qx(base, g2, years_g2, years_issue, mort)
    expected = [[0.01 * 1.1 * 0.99**13 * 1.0, 0.02 * 1.1 * 0.995**14 * 0.99]]
    np.testing.assert_allclose(qx, expected, rtol=1e-12)
    capped = hb.adjusted_annual_qx(np.array([[0.9]]), np.array([[0.0]]), np.array([0.0]),
                                   np.array([[0.0]]), MortalityConfig(mortality_multiplier=2.0))
    assert capped[0, 0] == 1.0


# ── Step 5 — In force ────────────────────────────────────────────────────────


def test_step5_in_force_survivorship():
    q = np.full((1, 4), 0.01)
    lapse = np.full((1, 4), 0.04)
    bop, survivors = hb.in_force(q, lapse, maturity_period=np.array([10]))
    np.testing.assert_allclose(bop, [[1.0, 0.95, 0.95**2, 0.95**3]])
    np.testing.assert_allclose(survivors, [[0.95, 0.95**2, 0.95**3, 0.95**4]])


def test_step5_in_force_stops_after_maturity():
    q = np.full((2, 5), 0.01)
    lapse = np.zeros((2, 5))
    bop, survivors = hb.in_force(q, lapse, maturity_period=np.array([1, 4]))
    np.testing.assert_allclose(bop[0], [1.0, 0.99, 0.0, 0.0, 0.0])
    np.testing.assert_allclose(survivors[0], [0.99, 0.99**2, 0.0, 0.0, 0.0])
    assert (bop[1] > 0).all()


def test_step5_in_force_survival_floored_at_zero():
    bop, survivors = hb.in_force(np.array([[0.7, 0.1]]), np.array([[0.6, 0.1]]), np.array([5]))
    np.testing.assert_allclose(bop, [[1.0, 0.0]])
    np.testing.assert_allclose(survivors, [[0.0, 0.0]])


# ── Step 6 — Account value ───────────────────────────────────────────────────


def test_step6_account_value_per_policy():
    i = np.array([0.01])
    w = np.array([[0.0, 0.1, 0.0]])
    bop, mid, eop = hb.account_value_per_policy(np.array([1000.0]), i, w)
    np.testing.assert_allclose(bop, [[1000.0, 1010.0, 1010.0 * 1.01 * 0.9]])
    np.testing.assert_allclose(mid, bop * 1.01)
    np.testing.assert_allclose(eop, mid * (1 - w))


# ── Step 7 — Cash flows & full reconciliation ────────────────────────────────


@pytest.fixture(scope="module")
def projections():
    portfolio, config = _portfolio(), _config()
    mine = hb.project(portfolio, config, VAL_DATE, projection_horizon_years=12)
    reference = benchmark.project(portfolio, config, VAL_DATE, projection_horizon_years=12)
    return mine, reference


def test_step7_cash_flows():
    flows = hb.cash_flows(
        in_force_bop=np.array([[1.0, 0.9]]),
        survivors=np.array([[0.9, 0.8]]),
        monthly_qx=np.array([[0.02, 0.02]]),
        monthly_lapse=np.array([[0.08, 0.09]]),
        av_bop=np.array([[100.0, 101.0]]),
        av_mid=np.array([[101.0, 102.0]]),
        av_eop=np.array([[101.0, 99.0]]),
        monthly_credit=np.array([0.01]),
        withdrawal_rate=np.array([[0.0, 0.03]]),
        surrender_charge_rate=np.array([[0.05, 0.05]]),
        single_premium=np.array([110.0]),
        death_benefit_is_rop=np.array([True]),
        maturity_period=np.array([1]),
    )
    assert set(flows) == set(CASH_FLOW_COLUMNS + COUNT_COLUMNS)
    np.testing.assert_allclose(flows["death_benefits"], [[0.02 * 110.0, 0.9 * 0.02 * 110.0]])
    np.testing.assert_allclose(flows["surrender_charge"], [[0.08 * 101 * 0.05, 0.9 * 0.09 * 102 * 0.05]])
    np.testing.assert_allclose(flows["maturity_benefits"], [[0.0, 0.8 * 99.0]])
    np.testing.assert_allclose(flows["lives_in_force"], [[0.9, 0.0]])
    np.testing.assert_allclose(flows["account_value_eop"], [[0.9 * 101.0, 0.0]])


def test_reconciles_to_gaspatchio(projections):
    """The milestone: hand-built engine == gaspatchio benchmark, every policy, line, month."""
    mine, reference = projections
    assert mine.policy_ids == reference.policy_ids
    for column in CASH_FLOW_COLUMNS + COUNT_COLUMNS:
        np.testing.assert_allclose(
            np.array(mine.frame[column].to_list()),
            np.array(reference.frame[column].to_list()),
            rtol=1e-12,
            atol=1e-8,
            err_msg=column,
        )


def test_seriatim_routes_to_handbuilt_engine():
    from actuarial_model.engine import seriatim

    projection = seriatim.project(_portfolio()[:1], _config(), VAL_DATE, engine="handbuilt")
    assert projection.methodology_version == hb.METHODOLOGY_VERSION

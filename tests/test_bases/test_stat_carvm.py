"""Tests for STAT Pre-VM-22 CARVM (gaspatchio greatest-PV model).

CARVM = greatest present value of future guaranteed benefits. These tests
pin the model to hand-calculable closed forms:

  - guaranteed AV at month m:  AV0 * (1+g)^(m/12)
  - discounted at i_val:       PV(m) = AV0 * ((1+g)/(1+i))^(m/12) * (1-sc)
"""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import Basis, Framework
from actuarial_model.assumptions.sets import StatCarvmConfig
from actuarial_model.bases.stat import carvm
from tests.factories import policy, stamp


def _run(policies, i_val: float, run_id: str = "RUN-1"):
    return carvm.calculate(
        policies, StatCarvmConfig(valuation_interest_rate=i_val), stamp(run_id=run_id)
    )


def _reserve(policies, i_val: float) -> float:
    return _run(policies, i_val).reserve_result.gross_reserve


def _audit(p, i_val: float) -> dict:
    audit = _run([p], i_val).extras["policy_audit"]
    return audit.filter(audit["policy_id"] == p.policy_id).to_dicts()[0]


def test_equal_rates_no_charges_reserve_equals_av():
    assert _reserve([policy(guaranteed_rate=0.03)], i_val=0.03) == pytest.approx(100_000.0, rel=1e-9)


def test_crediting_above_valuation_rate_maturity_governs():
    expected = 100_000.0 * (1.04 / 1.03) ** 5
    p = policy(guaranteed_rate=0.04)
    assert _reserve([p], i_val=0.03) == pytest.approx(expected, rel=1e-9)
    assert _audit(p, 0.03)["greatest_pv_month"] == 60


def test_crediting_below_valuation_rate_current_csv_governs():
    p = policy(guaranteed_rate=0.02)
    assert _reserve([p], i_val=0.05) == pytest.approx(100_000.0, rel=1e-9)
    assert _audit(p, 0.05)["greatest_pv_month"] == 0


def test_surrender_charges_reduce_reserve_to_csv_floor():
    p = policy(surrender_charge_schedule_id="ATHENE_MYG_5")
    assert _reserve([p], i_val=0.10) == pytest.approx(92_000.0, rel=1e-9)
    audit = _audit(p, 0.10)
    assert audit["csv_at_valuation"] == pytest.approx(92_000.0)
    assert audit["greatest_pv_month"] == 0


def test_charges_with_high_crediting_maturity_still_governs():
    expected = 100_000.0 * (1.04 / 1.03) ** 5
    p = policy(guaranteed_rate=0.04, surrender_charge_schedule_id="ATHENE_MYG_5")
    assert _reserve([p], i_val=0.03) == pytest.approx(expected, rel=1e-9)


def test_reserve_never_below_current_csv():
    for i_val in (0.01, 0.04, 0.08, 0.15):
        audit = _audit(policy(surrender_charge_schedule_id="ATHENE_MYG_5"), i_val)
        assert audit["reserve"] >= audit["csv_at_valuation"] - 1e-9


def test_removing_charges_weakly_increases_reserve():
    with_sc = _reserve([policy(surrender_charge_schedule_id="ATHENE_MYG_5")], i_val=0.05)
    assert _reserve([policy()], i_val=0.05) >= with_sc


def test_matured_policy_reserve_is_account_value():
    p = policy(issue_date=date(2019, 1, 1), guarantee_period_years=5)
    assert _reserve([p], i_val=0.05) == pytest.approx(100_000.0)
    audit = _audit(p, 0.05)
    assert audit["months_to_maturity"] == 0
    assert audit["csv_at_valuation"] == pytest.approx(100_000.0)


def test_mid_term_policy_uses_correct_policy_year_charge():
    """2 years into a 5-year guarantee → ATHENE_MYG_5 year-3 charge (6%)."""
    p = policy(issue_date=date(2023, 1, 1), surrender_charge_schedule_id="ATHENE_MYG_5")
    assert _audit(p, 0.15)["csv_at_valuation"] == pytest.approx(94_000.0)


def test_multiple_policies_sum_and_detail_is_per_policy():
    result = _run(
        [policy("A"), policy("B", account_value=50_000.0)], i_val=0.03
    )
    assert result.reserve_result.gross_reserve == pytest.approx(150_000.0, rel=1e-9)
    detail = {r["policy_id"]: r["gross"] for r in result.policy_detail.to_dicts()}
    assert detail == {"A": pytest.approx(100_000.0), "B": pytest.approx(50_000.0)}


def test_metadata_and_components():
    result = _run([policy()], i_val=0.04, run_id="RUN-CARVM-1").reserve_result
    assert result.metadata.framework is Framework.STAT_CARVM
    assert result.metadata.basis is Basis.STAT
    assert result.metadata.run_id == "RUN-CARVM-1"
    assert result.net_reserve == result.gross_reserve
    assert result.ceded_reserve == 0.0
    assert result.components["valuation_interest_rate"] == 0.04
    assert result.components["policy_count"] == 1
    assert result.legal_entity == "ENT-A"


def test_empty_policy_list_zero_reserve():
    result = _run([], i_val=0.04).reserve_result
    assert result.gross_reserve == 0.0
    assert result.legal_entity == "ALL"

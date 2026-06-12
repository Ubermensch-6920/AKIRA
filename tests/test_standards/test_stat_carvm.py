"""Tests for the Pre-VM-22 CARVM reserve module.

CARVM = greatest present value of future guaranteed benefits. These tests
pin the engine to hand-calculable closed forms:

  - guaranteed AV at month m:  AV0 * (1+g)^(m/12)
  - discounted at i_val:       PV(m) = AV0 * ((1+g)/(1+i))^(m/12) * (1-sc)
"""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import Framework
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.models.policy import MygaPolicyState
from actuarial_model.standards.stat_carvm import StatCarvmInput, calculate

VAL_DATE = date(2025, 1, 1)


def _aset(i_val: float) -> AssumptionSet:
    a = AssumptionSet(
        assumption_set_id="carvm-test",
        version="0.1.0",
        description="CARVM test set",
        created_by="pytest",
        created_date=VAL_DATE,
    )
    a.stat_carvm.valuation_interest_rate = i_val
    return a


def _policy(
    *,
    account_value: float = 100_000.0,
    guaranteed_rate: float = 0.03,
    guarantee_period_years: int = 5,
    issue_date: date = VAL_DATE,
    valuation_date: date = VAL_DATE,
    surrender_charge_schedule_id: str = "NONE",  # unknown ID -> no charges
    policy_id: str = "CARVM-1",
) -> MygaPolicyState:
    return MygaPolicyState(
        policy_id=policy_id,
        issue_date=issue_date,
        issue_age=60,
        sex="M",
        issue_state="NY",
        legal_entity="ENT-A",
        segment="MYGA-RETAIL",
        cohort_id="2025Q1",
        valuation_date=valuation_date,
        single_premium=account_value,
        account_value=account_value,
        guaranteed_rate=guaranteed_rate,
        guarantee_period_years=guarantee_period_years,
        guarantee_end_date=date(
            issue_date.year + guarantee_period_years, issue_date.month, issue_date.day
        ),
        surrender_charge_schedule_id=surrender_charge_schedule_id,
    )


def _reserve(policies: list[MygaPolicyState], i_val: float) -> float:
    output = calculate(
        StatCarvmInput(
            assumption_set=_aset(i_val), policies=policies, valuation_date=VAL_DATE
        )
    )
    return output.reserve_result.gross_reserve


def _detail(policy: MygaPolicyState, i_val: float) -> dict:
    output = calculate(
        StatCarvmInput(
            assumption_set=_aset(i_val), policies=[policy], valuation_date=VAL_DATE
        )
    )
    return output.reserve_result.components["policy_detail"][policy.policy_id]


# ---------------------------------------------------------------------------
# Closed-form hand calculations
# ---------------------------------------------------------------------------


def test_equal_rates_no_charges_reserve_equals_av():
    """g == i and no surrender charges: every PV equals AV, so reserve = AV."""
    reserve = _reserve([_policy(guaranteed_rate=0.03)], i_val=0.03)
    assert reserve == pytest.approx(100_000.0, rel=1e-9)


def test_crediting_above_valuation_rate_maturity_governs():
    """g > i: PV grows with time, so the maturity benefit governs.

    Reserve = AV * ((1+g)/(1+i))^T = 100,000 * (1.04/1.03)^5.
    """
    expected = 100_000.0 * (1.04 / 1.03) ** 5
    policy = _policy(guaranteed_rate=0.04)
    reserve = _reserve([policy], i_val=0.03)
    assert reserve == pytest.approx(expected, rel=1e-9)

    detail = _detail(policy, i_val=0.03)
    assert detail["greatest_pv_month"] == 60  # maturity month governs


def test_crediting_below_valuation_rate_current_csv_governs():
    """g < i and no charges: PV declines with time, so t=0 CSV (= AV) governs."""
    policy = _policy(guaranteed_rate=0.02)
    reserve = _reserve([policy], i_val=0.05)
    assert reserve == pytest.approx(100_000.0, rel=1e-9)

    detail = _detail(policy, i_val=0.05)
    assert detail["greatest_pv_month"] == 0


def test_surrender_charges_reduce_reserve_to_csv_floor():
    """High discount rate + Athene 5-year charges: reserve = current CSV.

    Year-1 charge on ATHENE_MYG_5 is 8%, so CSV floor = 92,000. Later months
    are discounted at 10% against 3% growth and can't beat it.
    """
    policy = _policy(surrender_charge_schedule_id="ATHENE_MYG_5")
    reserve = _reserve([policy], i_val=0.10)
    assert reserve == pytest.approx(92_000.0, rel=1e-9)

    detail = _detail(policy, i_val=0.10)
    assert detail["csv_at_valuation"] == pytest.approx(92_000.0)
    assert detail["greatest_pv_month"] == 0


def test_charges_with_high_crediting_maturity_still_governs():
    """g > i with charges: charges never apply at maturity, so the maturity
    PV is unchanged and still governs."""
    expected = 100_000.0 * (1.04 / 1.03) ** 5
    policy = _policy(
        guaranteed_rate=0.04, surrender_charge_schedule_id="ATHENE_MYG_5"
    )
    reserve = _reserve([policy], i_val=0.03)
    assert reserve == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Structural properties
# ---------------------------------------------------------------------------


def test_reserve_never_below_current_csv():
    """The t=0 candidate makes current CSV a hard floor on the reserve."""
    for i_val in (0.01, 0.04, 0.08, 0.15):
        policy = _policy(surrender_charge_schedule_id="ATHENE_MYG_5")
        detail = _detail(policy, i_val=i_val)
        assert detail["reserve"] >= detail["csv_at_valuation"] - 1e-9


def test_removing_charges_weakly_increases_reserve():
    """Without charges every candidate benefit is >= the charged one."""
    with_sc = _reserve(
        [_policy(surrender_charge_schedule_id="ATHENE_MYG_5")], i_val=0.05
    )
    without_sc = _reserve([_policy()], i_val=0.05)
    assert without_sc >= with_sc


def test_matured_policy_reserve_is_account_value():
    """Valuation on/after guarantee end: reserve = full AV."""
    policy = _policy(
        issue_date=date(2019, 1, 1),
        guarantee_period_years=5,  # guarantee ended 2024-01-01, before VAL_DATE
        valuation_date=VAL_DATE,
    )
    reserve = _reserve([policy], i_val=0.05)
    assert reserve == pytest.approx(100_000.0)
    assert _detail(policy, i_val=0.05)["months_to_maturity"] == 0


def test_mid_term_policy_uses_correct_policy_year_charge():
    """A policy 2 years into a 5-year guarantee picks up the year-3 charge.

    ATHENE_MYG_5 year-3 charge is 6%, so CSV floor = 94,000 at high i_val.
    """
    policy = _policy(
        issue_date=date(2023, 1, 1),  # valuation 2025-01-01 = start of policy year 3
        guarantee_period_years=5,
        surrender_charge_schedule_id="ATHENE_MYG_5",
    )
    detail = _detail(policy, i_val=0.15)
    assert detail["csv_at_valuation"] == pytest.approx(94_000.0)


# ---------------------------------------------------------------------------
# Aggregation & metadata
# ---------------------------------------------------------------------------


def test_multiple_policies_sum():
    p1 = _policy(policy_id="A", guaranteed_rate=0.03)
    p2 = _policy(policy_id="B", guaranteed_rate=0.03, account_value=50_000.0)
    total = _reserve([p1, p2], i_val=0.03)
    assert total == pytest.approx(150_000.0, rel=1e-9)


def test_metadata_and_components():
    output = calculate(
        StatCarvmInput(
            assumption_set=_aset(0.04),
            policies=[_policy()],
            valuation_date=VAL_DATE,
            run_id="RUN-CARVM-1",
        )
    )
    result = output.reserve_result
    assert result.metadata.framework is Framework.STAT_CARVM
    assert result.metadata.run_id == "RUN-CARVM-1"
    assert result.net_reserve == result.gross_reserve
    assert result.ceded_reserve == 0.0
    assert result.components["valuation_interest_rate"] == 0.04
    assert result.components["policy_count"] == 1
    assert result.legal_entity == "ENT-A"


def test_empty_policy_list_zero_reserve():
    output = calculate(
        StatCarvmInput(
            assumption_set=_aset(0.04), policies=[], valuation_date=VAL_DATE
        )
    )
    assert output.reserve_result.gross_reserve == 0.0
    assert output.reserve_result.legal_entity == "ALL"

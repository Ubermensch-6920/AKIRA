"""Product-document alignment tests (Athene MYG doc 76009 / MaxRate doc 76047).

Covers the two provisions wired from the product documents:
  - Free-withdrawal basis: MYG frees 10% of AV; MaxRate frees the
    interest earned (fixed strategy rate x AV).
  - Nonforfeiture: cash surrender values floor at the Minimum Guaranteed
    Surrender Value (87.5% of premium accumulated at the nonforfeiture
    rate).
"""

from datetime import date

import pytest

from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.core.projections.myga import MygaProjectionInput, calculate
from actuarial_model.models.policy import MygaPolicyState
from actuarial_model.standards.stat_carvm import StatCarvmInput
from actuarial_model.standards.stat_carvm import calculate as carvm_calculate
from actuarial_model.withdrawal.calculator import WithdrawalCalculator
from actuarial_model.withdrawal.rates import FreeWithdrawalConfig

VAL_DATE = date(2025, 1, 1)


def _policy(**overrides) -> MygaPolicyState:
    fields: dict = dict(
        policy_id="ALIGN-1",
        issue_date=VAL_DATE,
        issue_age=60,
        sex="M",
        issue_state="TX",
        legal_entity="ENT-A",
        segment="MYGA-RETAIL",
        cohort_id="2025Q1",
        valuation_date=VAL_DATE,
        single_premium=100_000.0,
        account_value=100_000.0,
        guaranteed_rate=0.03,
        guarantee_period_years=5,
        guarantee_end_date=date(2030, 1, 1),
        surrender_charge_schedule_id="NONE",
    )
    fields.update(overrides)
    return MygaPolicyState(**fields)


def _carvm_aset(i_val: float) -> AssumptionSet:
    a = AssumptionSet(
        assumption_set_id="align-test",
        version="0.1.0",
        description="Product alignment test set",
        created_by="pytest",
        created_date=VAL_DATE,
    )
    a.stat_carvm.valuation_interest_rate = i_val
    return a


# ── Free-withdrawal basis ─────────────────────────────────────────────────
def test_free_withdrawal_fraction_by_basis():
    myg = _policy(free_withdrawal_basis="PCT_AV", free_withdrawal_pct=0.10)
    maxrate = _policy(free_withdrawal_basis="INTEREST_EARNED", guaranteed_rate=0.045)
    assert myg.free_withdrawal_fraction() == 0.10
    assert maxrate.free_withdrawal_fraction() == 0.045


def test_calculator_interest_earned_basis():
    """MaxRate free amount = credited rate x AV, ignoring annual_free_pct."""
    config = FreeWithdrawalConfig(basis="INTEREST_EARNED", annual_free_pct=0.10)
    amount = WithdrawalCalculator.free_withdrawal_amount(
        100_000.0, config, policy_year=1, credited_rate=0.045
    )
    assert amount == pytest.approx(4_500.0)
    # PCT_AV default keeps the historic behavior.
    pct_config = FreeWithdrawalConfig(annual_free_pct=0.10)
    assert WithdrawalCalculator.free_withdrawal_amount(
        100_000.0, pct_config, policy_year=1
    ) == pytest.approx(10_000.0)


def test_engine_interest_earned_corridor_drains_less(
    sample_assumption_set: AssumptionSet,
):
    """A MaxRate-style policy (3% interest corridor) withdraws less than a
    MYG-style policy (10% of AV corridor), all else equal."""
    myg = _policy(policy_id="MYG", free_withdrawal_basis="PCT_AV")
    maxrate = _policy(policy_id="MAXRATE", free_withdrawal_basis="INTEREST_EARNED")
    output = calculate(
        MygaProjectionInput(
            assumption_set=sample_assumption_set,
            policies=[myg, maxrate],
            valuation_date=VAL_DATE,
        )
    )
    by_id = {p.policy_id: p for p in output.cash_flows.policies}
    myg_withdrawals = sum(r.partial_withdrawals for r in by_id["MYG"].records)
    maxrate_withdrawals = sum(r.partial_withdrawals for r in by_id["MAXRATE"].records)
    assert maxrate_withdrawals < myg_withdrawals
    # Corridor ratio ~ 3%/10% on identical behavior rates and near-identical AV.
    assert maxrate_withdrawals == pytest.approx(myg_withdrawals * 0.3, rel=0.05)


# ── MGSV nonforfeiture floor ──────────────────────────────────────────────
def test_mgsv_accumulation():
    policy = _policy(nonforfeiture_rate=0.01)
    assert policy.mgsv_at(0) == pytest.approx(87_500.0)
    assert policy.mgsv_at(24) == pytest.approx(87_500.0 * 1.01**2)


def test_engine_mgsv_floors_surrender_benefits(sample_assumption_set: AssumptionSet):
    """With AV depleted below the MGSV, lapsing policies receive the MGSV:
    surrender benefits exceed the no-floor twin and no charge is collected."""
    floored = _policy(
        policy_id="FLOORED",
        account_value=80_000.0,  # below 87.5% of the 100k premium
        guaranteed_rate=0.0,
        issue_date=date(2023, 1, 1),
        guarantee_end_date=date(2028, 1, 1),
    )
    no_floor = floored.model_copy(
        update={"policy_id": "NOFLOOR", "mgsv_premium_pct": 0.0}
    )
    output = calculate(
        MygaProjectionInput(
            assumption_set=sample_assumption_set,
            policies=[floored, no_floor],
            valuation_date=VAL_DATE,
        )
    )
    by_id = {p.policy_id: p for p in output.cash_flows.policies}
    floored_sv = sum(r.surrender_benefits for r in by_id["FLOORED"].records)
    no_floor_sv = sum(r.surrender_benefits for r in by_id["NOFLOOR"].records)
    assert floored_sv > no_floor_sv
    # Floor binds from period 1, so no surrender charge is ever collected.
    assert all(r.surrender_charge == 0.0 for r in by_id["FLOORED"].records)


def test_carvm_mgsv_floor_binds():
    """AV 80k against a 100k-premium MGSV: the reserve is the discounted
    MGSV at maturity, not the account value."""
    policy = _policy(
        account_value=80_000.0,
        guaranteed_rate=0.0,
        issue_date=date(2023, 1, 1),
        guarantee_period_years=4,
        guarantee_end_date=date(2027, 1, 1),
    )
    output = carvm_calculate(
        StatCarvmInput(
            assumption_set=_carvm_aset(0.0),
            policies=[policy],
            valuation_date=VAL_DATE,
        )
    )
    # 48 months from issue at the 1% nonforfeiture rate, undiscounted (i=0).
    assert output.reserve_result.gross_reserve == pytest.approx(
        87_500.0 * 1.01**4, rel=1e-6
    )


def test_carvm_matured_policy_mgsv_floor():
    """A matured policy reserves max(AV, MGSV)."""
    policy = _policy(
        account_value=80_000.0,
        guaranteed_rate=0.0,
        issue_date=date(2015, 1, 1),
        guarantee_period_years=5,
        guarantee_end_date=date(2020, 1, 1),
    )
    output = carvm_calculate(
        StatCarvmInput(
            assumption_set=_carvm_aset(0.04),
            policies=[policy],
            valuation_date=VAL_DATE,
        )
    )
    # 120 months since issue at 1%.
    assert output.reserve_result.gross_reserve == pytest.approx(
        87_500.0 * 1.01**10, rel=1e-6
    )


def test_carvm_floor_inert_when_av_healthy():
    """A healthy MYG policy (AV >= premium, positive crediting) is unaffected
    by the MGSV floor: reserve matches the no-floor twin."""
    policy = _policy(surrender_charge_schedule_id="ATHENE_MYG_5")
    twin = policy.model_copy(update={"mgsv_premium_pct": 0.0})
    with_floor = carvm_calculate(
        StatCarvmInput(
            assumption_set=_carvm_aset(0.04), policies=[policy], valuation_date=VAL_DATE
        )
    )
    without_floor = carvm_calculate(
        StatCarvmInput(
            assumption_set=_carvm_aset(0.04), policies=[twin], valuation_date=VAL_DATE
        )
    )
    assert with_floor.reserve_result.gross_reserve == pytest.approx(
        without_floor.reserve_result.gross_reserve, rel=1e-12
    )

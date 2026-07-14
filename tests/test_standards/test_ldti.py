"""Tests for the LDTI (LFPB + DAC) module."""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import DacBasis, Framework
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.core.discount import CurvePoint
from actuarial_model.models.cash_flows import (
    GrossCashFlows,
    MygaCashFlowRecord,
    PolicyCashFlows,
)
from actuarial_model.models.policy import MygaPolicyState
from actuarial_model.standards.ldti import LdtiInput, calculate

VAL_DATE = date(2025, 1, 1)


def _record(period: int, end: date, *, maturity: float = 0.0) -> MygaCashFlowRecord:
    return MygaCashFlowRecord(
        policy_id="P1",
        period=period,
        period_start_date=end,
        period_end_date=end,
        account_value_bop=0.0,
        interest_credited=0.0,
        partial_withdrawals=0.0,
        surrender_charge=0.0,
        mva_adjustment=0.0,
        surrender_benefits=0.0,
        death_benefits=0.0,
        maturity_benefits=maturity,
        account_value_eop=0.0,
        lives_in_force=1.0,
    )


def _cfs(records: list[MygaCashFlowRecord]) -> GrossCashFlows:
    return GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[PolicyCashFlows(policy_id="P1", records=records)],
    )


def _flat_curve(rate: float) -> list[CurvePoint]:
    return [
        CurvePoint(tenor_years=1.0, rate=rate),
        CurvePoint(tenor_years=30.0, rate=rate),
    ]


def _policy(issue: date = date(2024, 1, 1), premium: float = 100_000.0) -> MygaPolicyState:
    return MygaPolicyState(
        policy_id="P1",
        issue_date=issue,
        issue_age=60,
        sex="M",
        issue_state="NY",
        legal_entity="ENT-A",
        segment="MYGA-RETAIL",
        cohort_id="2024Q1",
        valuation_date=VAL_DATE,
        single_premium=premium,
        account_value=premium,
        guaranteed_rate=0.03,
        guarantee_period_years=5,
        guarantee_end_date=date(issue.year + 5, issue.month, issue.day),
        surrender_charge_schedule_id="NONE",
    )


def test_requires_cash_flows(sample_assumption_set: AssumptionSet):
    with pytest.raises(ValueError, match="gross_cash_flows"):
        calculate(LdtiInput(assumption_set=sample_assumption_set))


def test_requires_curve_points(sample_assumption_set: AssumptionSet):
    with pytest.raises(ValueError, match="curve_points"):
        calculate(
            LdtiInput(assumption_set=sample_assumption_set, gross_cash_flows=_cfs([]))
        )


def test_lfpb_hand_calculation(sample_assumption_set: AssumptionSet):
    """Single-premium contract: LFPB = PV of benefits at the single-A curve."""
    output = calculate(
        LdtiInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=_cfs([_record(1, date(2026, 1, 1), maturity=10_000.0)]),
            curve_points=_flat_curve(0.05),
        )
    )
    assert output.lfpb_result.gross_reserve == pytest.approx(10_000.0 / 1.05, rel=1e-3)
    assert output.lfpb_result.metadata.framework is Framework.LDTI
    assert output.lfpb_result.components["component"] == "LFPB"


def test_npr_reported_and_capped(sample_assumption_set: AssumptionSet):
    """PV benefits 120k on a 100k premium → uncapped NPR 1.2, capped at 1.0."""
    output = calculate(
        LdtiInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=_cfs([_record(1, date(2026, 1, 1), maturity=120_000.0)]),
            policies=[_policy()],
            curve_points=_flat_curve(0.0),
        )
    )
    components = output.lfpb_result.components
    assert components["net_premium_ratio_uncapped"] == pytest.approx(1.2)
    assert components["net_premium_ratio"] == pytest.approx(1.0)


def test_dac_straight_line(sample_assumption_set: AssumptionSet):
    """5% of a 100k premium, 12 of 60 months elapsed → DAC = 5,000 * 48/60."""
    assumption_set = sample_assumption_set.model_copy(deep=True)
    assumption_set.ldti.acquisition_cost_pct = 0.05
    output = calculate(
        LdtiInput(
            assumption_set=assumption_set,
            gross_cash_flows=_cfs([_record(1, date(2026, 1, 1), maturity=1_000.0)]),
            policies=[_policy(issue=date(2024, 1, 1))],
            curve_points=_flat_curve(0.04),
        )
    )
    assert output.dac_result.gross_reserve == pytest.approx(5_000.0 * 48 / 60)
    assert output.dac_result.components["sign_convention"] == "ASSET"


def test_dac_zero_without_acquisition_cost(sample_assumption_set: AssumptionSet):
    output = calculate(
        LdtiInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=_cfs([_record(1, date(2026, 1, 1), maturity=1_000.0)]),
            policies=[_policy()],
            curve_points=_flat_curve(0.04),
        )
    )
    assert output.dac_result.gross_reserve == 0.0


def test_dac_fully_amortized_after_term(sample_assumption_set: AssumptionSet):
    """A policy issued 6+ years ago has no unamortized DAC left."""
    assumption_set = sample_assumption_set.model_copy(deep=True)
    assumption_set.ldti.acquisition_cost_pct = 0.05
    output = calculate(
        LdtiInput(
            assumption_set=assumption_set,
            gross_cash_flows=_cfs([]),
            policies=[_policy(issue=date(2018, 1, 1))],
            curve_points=_flat_curve(0.04),
        )
    )
    assert output.dac_result.gross_reserve == 0.0


def test_egp_basis_not_implemented(sample_assumption_set: AssumptionSet):
    assumption_set = sample_assumption_set.model_copy(deep=True)
    assumption_set.ldti.dac_basis = DacBasis.EGP
    with pytest.raises(NotImplementedError, match="EGP"):
        calculate(
            LdtiInput(
                assumption_set=assumption_set,
                gross_cash_flows=_cfs([]),
                curve_points=_flat_curve(0.04),
            )
        )


def test_ceded_stream_reduces_net(sample_assumption_set: AssumptionSet):
    gross = _cfs([_record(1, date(2026, 1, 1), maturity=10_000.0)])
    ceded = _cfs([_record(1, date(2026, 1, 1), maturity=4_000.0)])
    output = calculate(
        LdtiInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=gross,
            ceded_cash_flows=ceded,
            curve_points=_flat_curve(0.04),
        )
    )
    result = output.lfpb_result
    assert result.ceded_reserve == pytest.approx(0.4 * result.gross_reserve, rel=1e-9)
    assert result.net_reserve == pytest.approx(result.gross_reserve - result.ceded_reserve)

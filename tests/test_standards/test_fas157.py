"""Tests for the ASC 820 (FAS 157) fair-value liability module."""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import (
    Fas157DiscountBasis,
    Framework,
    NonPerfRiskAdj,
    RiskMarginMethod,
)
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.core.discount import CurvePoint
from actuarial_model.models.cash_flows import (
    GrossCashFlows,
    MygaCashFlowRecord,
    PolicyCashFlows,
)
from actuarial_model.standards.fas157 import Fas157Input, calculate

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


def _one_payment() -> GrossCashFlows:
    return _cfs([_record(1, date(2026, 1, 1), maturity=10_000.0)])


def test_requires_cash_flows(sample_assumption_set: AssumptionSet):
    with pytest.raises(ValueError, match="gross_cash_flows"):
        calculate(Fas157Input(assumption_set=sample_assumption_set))


def test_requires_curve_points(sample_assumption_set: AssumptionSet):
    with pytest.raises(ValueError, match="curve_points"):
        calculate(
            Fas157Input(assumption_set=sample_assumption_set, gross_cash_flows=_cfs([]))
        )


def test_hand_calculation_ois_zero_npr(sample_assumption_set: AssumptionSet):
    """OIS basis, no own-credit: FV = base PV + CoC risk margin."""
    assumption_set = sample_assumption_set.model_copy(deep=True)
    assumption_set.fas157.discount_basis = Fas157DiscountBasis.OIS
    assumption_set.fas157.non_performance_risk = NonPerfRiskAdj.ZERO
    output = calculate(
        Fas157Input(
            assumption_set=assumption_set,
            gross_cash_flows=_one_payment(),
            curve_points=_flat_curve(0.04),
        )
    )
    result = output.reserve_result
    base_pv = result.components["base_pv"]
    duration = result.components["liability_duration_years"]
    assert base_pv == pytest.approx(10_000.0 / 1.04, rel=1e-3)
    assert duration == pytest.approx(1.0, abs=0.01)
    expected_rm = 0.06 * 0.03 * base_pv * duration
    assert result.components["risk_margin"] == pytest.approx(expected_rm, rel=1e-9)
    assert result.components["non_performance_adjustment"] == 0.0
    assert result.gross_reserve == pytest.approx(base_pv + expected_rm, rel=1e-9)
    assert result.metadata.framework is Framework.FAS157


def test_single_a_basis_discounts_more_than_ois(sample_assumption_set: AssumptionSet):
    def base_pv(basis: Fas157DiscountBasis) -> float:
        assumption_set = sample_assumption_set.model_copy(deep=True)
        assumption_set.fas157.discount_basis = basis
        assumption_set.fas157.non_performance_risk = NonPerfRiskAdj.ZERO
        output = calculate(
            Fas157Input(
                assumption_set=assumption_set,
                gross_cash_flows=_one_payment(),
                curve_points=_flat_curve(0.04),
            )
        )
        return output.reserve_result.components["base_pv"]

    assert base_pv(Fas157DiscountBasis.SINGLE_A) < base_pv(Fas157DiscountBasis.RF_ILLIQ)
    assert base_pv(Fas157DiscountBasis.RF_ILLIQ) < base_pv(Fas157DiscountBasis.OIS)


def test_own_credit_reduces_liability(sample_assumption_set: AssumptionSet):
    """OWN_CREDIT adjustment is negative and lowers the fair value."""
    def fair_value(treatment: NonPerfRiskAdj) -> tuple[float, float]:
        assumption_set = sample_assumption_set.model_copy(deep=True)
        assumption_set.fas157.non_performance_risk = treatment
        output = calculate(
            Fas157Input(
                assumption_set=assumption_set,
                gross_cash_flows=_one_payment(),
                curve_points=_flat_curve(0.04),
            )
        )
        result = output.reserve_result
        return result.gross_reserve, result.components["non_performance_adjustment"]

    fv_zero, adj_zero = fair_value(NonPerfRiskAdj.ZERO)
    fv_own, adj_own = fair_value(NonPerfRiskAdj.OWN_CREDIT)
    assert adj_zero == 0.0
    assert adj_own < 0.0
    assert fv_own < fv_zero


def test_non_coc_risk_margin_not_implemented(sample_assumption_set: AssumptionSet):
    assumption_set = sample_assumption_set.model_copy(deep=True)
    assumption_set.fas157.risk_margin_method = RiskMarginMethod.CALM
    with pytest.raises(NotImplementedError, match="CALM"):
        calculate(
            Fas157Input(
                assumption_set=assumption_set,
                gross_cash_flows=_cfs([]),
                curve_points=_flat_curve(0.04),
            )
        )


def test_ceded_scales_proportionally(sample_assumption_set: AssumptionSet):
    ceded = _cfs([_record(1, date(2026, 1, 1), maturity=4_000.0)])
    output = calculate(
        Fas157Input(
            assumption_set=sample_assumption_set,
            gross_cash_flows=_one_payment(),
            ceded_cash_flows=ceded,
            curve_points=_flat_curve(0.04),
        )
    )
    result = output.reserve_result
    assert result.ceded_reserve == pytest.approx(0.4 * result.gross_reserve, rel=1e-9)
    assert result.net_reserve == pytest.approx(result.gross_reserve - result.ceded_reserve)

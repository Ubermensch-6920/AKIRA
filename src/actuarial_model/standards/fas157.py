"""
ASC 820 fair-value liability calculation (formerly FAS 157).

Computes a fair-value liability with explicit risk margin (cost-of-
capital, CALM, or explicit), non-performance / own-credit risk
adjustment, and a configured discount basis.

Method (Phase 1):
  Fair value = base PV + risk margin + non-performance adjustment, where
    base PV — projected best-estimate liability outflows discounted on
      the supplied curve shifted by the discount-basis spread (OIS = 0,
      SINGLE_A / RF_ILLIQ = placeholder spreads below).
    risk margin — cost-of-capital proxy: coc_rate * (capital-ratio proxy
      * base PV) * liability duration. Stands in for a full projected-
      capital runoff (ASSUMPTION REQUIRED: capital ratio and spreads).
    non-performance adjustment — own-credit (or prescribed) spread added
      to the discount curve; the PV relief is reported as a negative
      adjustment. ZERO leaves the liability unadjusted.

Phase 1 simplifications (documented for review):
  - Risk margin methods CALM and EXPLICIT raise NotImplementedError.
  - ``mortality_loaded`` is not applied (no margin-loaded decrement
    basis exists yet).
  - ``measurement_date`` defaults to the valuation date.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.enums import (
    Fas157DiscountBasis,
    Framework,
    NonPerfRiskAdj,
    RiskMarginMethod,
)
from ..assumptions.sets import AssumptionSet
from ..core.discount import CurvePoint
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult, ResultMetadata
from .bel import _aggregate_labels, _discount_outflows, _pv_weighted_duration
from .stat_vm22 import _shifted_curve

METHODOLOGY_VERSION = "fas157_v0.1.0"

# ASSUMPTION REQUIRED: placeholder spreads (decimal) over the supplied curve.
_DISCOUNT_BASIS_SPREAD = {
    Fas157DiscountBasis.OIS: 0.0,
    Fas157DiscountBasis.SINGLE_A: 0.0080,
    Fas157DiscountBasis.RF_ILLIQ: 0.0050,
}
_OWN_CREDIT_SPREAD = 0.0050
_PRESCRIBED_NPR_SPREAD = 0.0025
# ASSUMPTION REQUIRED: capital held per unit of liability, for the
# cost-of-capital risk-margin proxy.
_CAPITAL_RATIO_PROXY = 0.03


class Fas157Input(BaseModel):
    """Inputs to the ASC 820 fair-value calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    ceded_cash_flows: GrossCashFlows | None = None  # from reinsurance.application
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None
    measurement_date: date | None = None  # ASC 820 measurement date (may differ from valuation_date)
    curve_points: list[CurvePoint] = []  # base risk-free curve
    run_id: str = ""


class Fas157Output(BaseModel):
    """Output of the ASC 820 fair-value calculation."""

    reserve_result: ReserveResult


def calculate(inputs: Fas157Input) -> Fas157Output:
    """Compute the ASC 820 fair-value liability.

    Raises:
        ValueError: If ``gross_cash_flows`` or ``curve_points`` are missing.
        NotImplementedError: For CALM / EXPLICIT risk-margin methods.
    """
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "Fas157Input.gross_cash_flows is required — run the projection "
            "engine (core.seriatim) first."
        )
    if not inputs.curve_points:
        raise ValueError("Fas157Input.curve_points is required for discounting.")

    config = inputs.assumption_set.fas157
    if config.risk_margin_method is not RiskMarginMethod.COST_OF_CAPITAL:
        raise NotImplementedError(
            f"Risk margin method {config.risk_margin_method.value} is not "
            "implemented in Phase 1 — use COST_OF_CAPITAL."
        )

    valuation_date = inputs.valuation_date or inputs.gross_cash_flows.valuation_date
    measurement_date = inputs.measurement_date or valuation_date

    basis_spread = _DISCOUNT_BASIS_SPREAD[config.discount_basis]
    base_curve = _shifted_curve(inputs.curve_points, basis_spread, valuation_date)

    policy_pv, _ = _discount_outflows(inputs.gross_cash_flows, base_curve, valuation_date)
    base_pv = sum(policy_pv.values())
    duration = _pv_weighted_duration(inputs.gross_cash_flows, base_curve, valuation_date)

    risk_margin = (
        config.cost_of_capital_rate * _CAPITAL_RATIO_PROXY * base_pv * duration
    )
    npr_adjustment = _non_performance_adjustment(
        inputs, config.non_performance_risk, basis_spread, base_pv, valuation_date
    )
    gross_fair_value = base_pv + risk_margin + npr_adjustment

    ceded_fair_value = 0.0
    if inputs.ceded_cash_flows is not None:
        policy_ceded_pv, _ = _discount_outflows(
            inputs.ceded_cash_flows, base_curve, valuation_date
        )
        ceded_base = sum(policy_ceded_pv.values())
        # Margin and own-credit scale proportionally with the ceded share.
        ceded_fair_value = (
            gross_fair_value * (ceded_base / base_pv) if base_pv > 0.0 else 0.0
        )

    legal_entity, segment, cohort_id = _aggregate_labels(inputs.policies)

    result = ReserveResult(
        metadata=ResultMetadata(
            valuation_date=valuation_date,
            framework=Framework.FAS157,
            methodology_version=METHODOLOGY_VERSION,
            run_id=inputs.run_id,
            assumption_set_id=inputs.assumption_set.assumption_set_id,
        ),
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        gross_reserve=gross_fair_value,
        ceded_reserve=ceded_fair_value,
        net_reserve=gross_fair_value - ceded_fair_value,
        components={
            "base_pv": base_pv,
            "risk_margin": risk_margin,
            "non_performance_adjustment": npr_adjustment,
            "liability_duration_years": duration,
            "discount_basis": config.discount_basis.value,
            "discount_basis_spread": basis_spread,
            "fair_value_level": config.fair_value_level.value,
            "risk_margin_method": config.risk_margin_method.value,
            "measurement_date": measurement_date.isoformat(),
            "policy_base_pv": policy_pv,
        },
    )
    return Fas157Output(reserve_result=result)


def _non_performance_adjustment(
    inputs: Fas157Input,
    treatment: NonPerfRiskAdj,
    basis_spread: float,
    base_pv: float,
    valuation_date: date,
) -> float:
    """PV relief from discounting at the own-credit / prescribed spread.

    Returned as a negative number (it reduces the liability); ZERO → 0.0.
    """
    if treatment is NonPerfRiskAdj.ZERO or base_pv == 0.0:
        return 0.0
    spread = (
        _OWN_CREDIT_SPREAD
        if treatment is NonPerfRiskAdj.OWN_CREDIT
        else _PRESCRIBED_NPR_SPREAD
    )
    assert inputs.gross_cash_flows is not None
    adjusted_curve = _shifted_curve(
        inputs.curve_points, basis_spread + spread, valuation_date
    )
    policy_pv, _ = _discount_outflows(
        inputs.gross_cash_flows, adjusted_curve, valuation_date
    )
    return sum(policy_pv.values()) - base_pv

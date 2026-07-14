"""
Bermuda Economic Balance Sheet (EBS) calculation.

Computes Technical Provisions (Standard approach), split into a best
estimate liability discounted at risk-free plus the configured
illiquidity premium, and a cost-of-capital risk margin.

Method (Phase 1):
  EBS BEL — projected best-estimate liability outflows discounted on the
    supplied risk-free curve shifted up by the illiquidity premium
    (BMA_PUBLISHED / INTERNAL use the placeholder constant below; ZERO
    uses the raw curve).
  Risk margin — cost-of-capital proxy: coc_rate * (capital-ratio proxy *
    EBS BEL) * liability duration, standing in for a projected BSCR
    runoff (ASSUMPTION REQUIRED).
  Technical provisions = EBS BEL + risk margin.
  Reinsurance — the ceded stream is discounted on the same curve; when
    ``apply_reinsurance_haircut`` is set, the ceded credit is reduced by
    ``reinsurance.bma_default_haircut_pct``.

Phase 1 simplifications (documented for review):
  - Scenario-Based Approach (SBA) raises NotImplementedError.
  - BSCR stresses (lapse, mortality improvement) are not run — the SCR
    itself is Phase 3 scope (capital/ecr.py).
  - Risk margin methods other than COST_OF_CAPITAL raise.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.enums import (
    EbsIlliquidityPremium,
    EbsTPApproach,
    Framework,
    RiskMarginMethod,
)
from ..assumptions.sets import AssumptionSet
from ..core.discount import CurvePoint
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult, ResultMetadata
from .bel import _aggregate_labels, _discount_outflows, _pv_weighted_duration
from .stat_vm22 import _shifted_curve

METHODOLOGY_VERSION = "ebs_v0.1.0"

# ASSUMPTION REQUIRED: placeholder illiquidity premium (decimal) until the
# BMA-published table is wired in.
_ILLIQUIDITY_PREMIUM = {
    EbsIlliquidityPremium.BMA_PUBLISHED: 0.0050,
    EbsIlliquidityPremium.INTERNAL: 0.0050,
    EbsIlliquidityPremium.ZERO: 0.0,
}
# ASSUMPTION REQUIRED: capital per unit of liability for the CoC proxy.
_CAPITAL_RATIO_PROXY = 0.03


class EbsInput(BaseModel):
    """Inputs to the EBS calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    ceded_cash_flows: GrossCashFlows | None = None  # from reinsurance.application
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None
    curve_points: list[CurvePoint] = []  # risk-free curve
    run_id: str = ""


class EbsOutput(BaseModel):
    """Output of the EBS calculation."""

    technical_provisions: ReserveResult
    risk_margin: ReserveResult


def calculate(inputs: EbsInput) -> EbsOutput:
    """Compute EBS technical provisions and risk margin.

    Raises:
        ValueError: If ``gross_cash_flows`` or ``curve_points`` are missing.
        NotImplementedError: For the SBA approach or non-CoC risk margins.
    """
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "EbsInput.gross_cash_flows is required — run the projection "
            "engine (core.seriatim) first."
        )
    if not inputs.curve_points:
        raise ValueError("EbsInput.curve_points is required for discounting.")

    config = inputs.assumption_set.ebs
    if config.tp_approach is not EbsTPApproach.STANDARD:
        raise NotImplementedError(
            f"TP approach {config.tp_approach.value} is not implemented in "
            "Phase 1 — use STANDARD."
        )
    if config.risk_margin_method is not RiskMarginMethod.COST_OF_CAPITAL:
        raise NotImplementedError(
            f"Risk margin method {config.risk_margin_method.value} is not "
            "implemented in Phase 1 — use COST_OF_CAPITAL."
        )

    valuation_date = inputs.valuation_date or inputs.gross_cash_flows.valuation_date
    illiquidity_premium = _ILLIQUIDITY_PREMIUM[config.illiquidity_premium]
    curve = _shifted_curve(inputs.curve_points, illiquidity_premium, valuation_date)

    policy_bel, _ = _discount_outflows(inputs.gross_cash_flows, curve, valuation_date)
    ebs_bel = sum(policy_bel.values())
    duration = _pv_weighted_duration(inputs.gross_cash_flows, curve, valuation_date)
    risk_margin = config.cost_of_capital_rate * _CAPITAL_RATIO_PROXY * ebs_bel * duration
    gross_tp = ebs_bel + risk_margin

    # ── Ceded credit (haircut per BMA counterparty treatment) ───────────
    ceded_bel = 0.0
    haircut_pct = 0.0
    if inputs.ceded_cash_flows is not None:
        policy_ceded, _ = _discount_outflows(
            inputs.ceded_cash_flows, curve, valuation_date
        )
        ceded_bel = sum(policy_ceded.values())
        if config.apply_reinsurance_haircut:
            haircut_pct = inputs.assumption_set.reinsurance.bma_default_haircut_pct
            ceded_bel *= 1.0 - haircut_pct
    # Risk margin is held on the same gross/ceded proportion as the BEL.
    ceded_tp = gross_tp * (ceded_bel / ebs_bel) if ebs_bel > 0.0 else 0.0

    legal_entity, segment, cohort_id = _aggregate_labels(inputs.policies)
    metadata = ResultMetadata(
        valuation_date=valuation_date,
        framework=Framework.EBS,
        methodology_version=METHODOLOGY_VERSION,
        run_id=inputs.run_id,
        assumption_set_id=inputs.assumption_set.assumption_set_id,
    )

    technical_provisions = ReserveResult(
        metadata=metadata,
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        gross_reserve=gross_tp,
        ceded_reserve=ceded_tp,
        net_reserve=gross_tp - ceded_tp,
        components={
            "component": "TECHNICAL_PROVISIONS",
            "ebs_bel": ebs_bel,
            "risk_margin": risk_margin,
            "illiquidity_premium": illiquidity_premium,
            "liability_duration_years": duration,
            "tp_approach": config.tp_approach.value,
            "reinsurance_haircut_pct": haircut_pct,
            "policy_ebs_bel": policy_bel,
        },
    )
    risk_margin_result = ReserveResult(
        metadata=metadata,
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        gross_reserve=risk_margin,
        ceded_reserve=0.0,
        net_reserve=risk_margin,
        components={
            "component": "RISK_MARGIN",
            "cost_of_capital_rate": config.cost_of_capital_rate,
            "capital_ratio_proxy": _CAPITAL_RATIO_PROXY,
            "liability_duration_years": duration,
        },
    )
    return EbsOutput(
        technical_provisions=technical_provisions, risk_margin=risk_margin_result
    )

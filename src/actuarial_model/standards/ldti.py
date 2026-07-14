"""
ASC 944 Long-Duration Targeted Improvements (LDTI) reserve calculation.

Computes the Liability for Future Policy Benefits (LFPB) using a net
premium ratio capped per configuration, plus the Deferred Acquisition
Cost (DAC) balance amortized on a straight-line basis (post-LDTI) or an
EGP basis (legacy).

Method (Phase 1, single-premium MYGA):
  LFPB — NPR-mechanics collapse for a single-premium contract: there are
    no future premiums after issue, so LFPB = PV of future benefit
    outflows discounted on the supplied upper-medium-grade (single-A)
    curve. The net premium ratio is still computed and capped
    (NPR = min(PV benefits / premium, cap)) and reported for disclosure,
    but with zero future premiums it does not alter the liability.
  DAC — deferrable cost = ``acquisition_cost_pct`` * single premium per
    policy, amortized straight-line over the guarantee period on a
    constant-basis (no interest) schedule per post-LDTI rules. Reported
    as a separate result: DAC is an asset, not a reserve.

Phase 1 simplifications (documented for review):
  - ``cohort_granularity`` is not applied — each run is one cohort.
  - The EGP (legacy) DAC basis raises NotImplementedError.
  - The supplied ``curve_points`` are taken as the discount-source curve
    (``discount_source`` is a label; no live market feed exists yet).
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.enums import DacBasis, Framework
from ..assumptions.sets import AssumptionSet
from ..core.discount import CurvePoint
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult, ResultMetadata
from .bel import _aggregate_labels, _discount_outflows
from .stat_carvm import _months_between
from .stat_vm22 import _shifted_curve

METHODOLOGY_VERSION = "ldti_v0.1.0"


class LdtiInput(BaseModel):
    """Inputs to the LDTI calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    ceded_cash_flows: GrossCashFlows | None = None  # from reinsurance.application
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None
    transition_date: date | None = None  # ASC 944 entity-level transition date
    curve_points: list[CurvePoint] = []  # upper-medium-grade discount curve
    run_id: str = ""


class LdtiOutput(BaseModel):
    """Output of the LDTI calculation: LFPB and DAC results."""

    lfpb_result: ReserveResult
    dac_result: ReserveResult


def calculate(inputs: LdtiInput) -> LdtiOutput:
    """Compute LDTI LFPB and DAC.

    Raises:
        ValueError: If ``gross_cash_flows`` or ``curve_points`` are missing.
        NotImplementedError: For the EGP (legacy) DAC basis.
    """
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "LdtiInput.gross_cash_flows is required — run the projection "
            "engine (core.seriatim) first."
        )
    if not inputs.curve_points:
        raise ValueError("LdtiInput.curve_points is required for discounting.")

    config = inputs.assumption_set.ldti
    if config.dac_basis is not DacBasis.STRAIGHT_LINE:
        raise NotImplementedError(
            f"DAC basis {config.dac_basis.value} is not implemented in "
            "Phase 1 — use STRAIGHT_LINE."
        )

    valuation_date = inputs.valuation_date or inputs.gross_cash_flows.valuation_date
    curve = _shifted_curve(inputs.curve_points, 0.0, valuation_date)

    # ── LFPB ─────────────────────────────────────────────────────────────
    policy_lfpb, _ = _discount_outflows(inputs.gross_cash_flows, curve, valuation_date)
    gross_lfpb = sum(policy_lfpb.values())

    total_premium = sum(p.single_premium for p in inputs.policies)
    raw_npr = gross_lfpb / total_premium if total_premium > 0.0 else None
    net_premium_ratio = (
        min(raw_npr, config.net_premium_ratio_cap) if raw_npr is not None else None
    )

    ceded_lfpb = 0.0
    if inputs.ceded_cash_flows is not None:
        policy_ceded, _ = _discount_outflows(
            inputs.ceded_cash_flows, curve, valuation_date
        )
        ceded_lfpb = sum(policy_ceded.values())

    # ── DAC ──────────────────────────────────────────────────────────────
    policy_dac = {
        p.policy_id: _straight_line_dac(p, config.acquisition_cost_pct, valuation_date)
        for p in inputs.policies
    }
    dac_balance = sum(policy_dac.values())

    legal_entity, segment, cohort_id = _aggregate_labels(inputs.policies)
    metadata = ResultMetadata(
        valuation_date=valuation_date,
        framework=Framework.LDTI,
        methodology_version=METHODOLOGY_VERSION,
        run_id=inputs.run_id,
        assumption_set_id=inputs.assumption_set.assumption_set_id,
    )

    lfpb_result = ReserveResult(
        metadata=metadata,
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        gross_reserve=gross_lfpb,
        ceded_reserve=ceded_lfpb,
        net_reserve=gross_lfpb - ceded_lfpb,
        components={
            "component": "LFPB",
            "net_premium_ratio": net_premium_ratio,
            "net_premium_ratio_uncapped": raw_npr,
            "net_premium_ratio_cap": config.net_premium_ratio_cap,
            "discount_source": config.discount_source.value,
            "policy_lfpb": policy_lfpb,
        },
    )
    dac_result = ReserveResult(
        metadata=metadata,
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        gross_reserve=dac_balance,
        ceded_reserve=0.0,
        net_reserve=dac_balance,
        components={
            "component": "DAC",
            "sign_convention": "ASSET",
            "dac_basis": config.dac_basis.value,
            "acquisition_cost_pct": config.acquisition_cost_pct,
            "policy_dac": policy_dac,
        },
    )
    return LdtiOutput(lfpb_result=lfpb_result, dac_result=dac_result)


def _straight_line_dac(
    policy: MygaPolicyState, acquisition_cost_pct: float, valuation_date: date
) -> float:
    """Unamortized DAC for one policy (straight-line over the guarantee term)."""
    deferrable = acquisition_cost_pct * policy.single_premium
    if deferrable <= 0.0:
        return 0.0
    total_months = policy.guarantee_period_years * 12
    if total_months <= 0:
        return 0.0
    elapsed = _months_between(policy.issue_date, valuation_date)
    remaining_fraction = 1.0 - min(max(elapsed, 0), total_months) / total_months
    return deferrable * remaining_fraction

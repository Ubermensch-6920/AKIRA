"""
Best Estimate Liability calculation module.

BEL = sum of best-estimate liability cash flows discounted at the
risk-free curve. Cross-cutting input to EBS, FAS 157, and serves as a
management-view comparator for STAT and LDTI.

Phase 1 scope:
  - Liability outflows per period = death benefits + surrender benefits
    + partial withdrawals + maturity benefits, assumed paid at period end.
  - Only cash flows falling strictly after the valuation date contribute.
  - No reinsurance applied yet, so ceded BEL = 0 and net = gross.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.enums import Framework
from ..assumptions.sets import AssumptionSet
from ..core.discount import CurvePoint, DiscountInput, build_curve
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult, ResultMetadata

METHODOLOGY_VERSION = "bel_v0.1.0"


class BelInput(BaseModel):
    """Inputs to the BEL calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None
    curve_points: list[CurvePoint] = []  # raw yield curve data for discounting
    run_id: str = ""


class BelOutput(BaseModel):
    """Output of the BEL calculation."""

    reserve_result: ReserveResult


def calculate(inputs: BelInput) -> BelOutput:
    """Compute Best Estimate Liability per the configured BEL config.

    Discounts each policy's projected liability outflows at the supplied
    risk-free curve and aggregates to a single :class:`ReserveResult`.
    Per-policy BELs are reported in ``components["policy_bel"]``.

    Raises:
        ValueError: If ``gross_cash_flows`` or ``curve_points`` are missing.
    """
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "BelInput.gross_cash_flows is required — run the projection "
            "engine (core.seriatim) first."
        )
    if not inputs.curve_points:
        raise ValueError("BelInput.curve_points is required for discounting.")

    bel_config = inputs.assumption_set.bel
    valuation_date = inputs.valuation_date or inputs.gross_cash_flows.valuation_date

    curve = build_curve(
        DiscountInput(
            valuation_date=valuation_date,
            curve=bel_config.risk_free_curve,
            interpolation=bel_config.curve_interpolation,
            curve_points=inputs.curve_points,
        )
    )

    policy_bel: dict[str, float] = {}
    total_outflows_undiscounted = 0.0

    for policy_cf in inputs.gross_cash_flows.policies:
        pv = 0.0
        for record in policy_cf.records:
            if record.period_end_date <= valuation_date:
                continue
            outflow = (
                record.death_benefits
                + record.surrender_benefits
                + record.partial_withdrawals
                + record.maturity_benefits
            )
            total_outflows_undiscounted += outflow
            pv += outflow * curve.discount_factor_for_date(record.period_end_date)
        policy_bel[policy_cf.policy_id] = pv

    gross_bel = sum(policy_bel.values())

    # Cohort labels come from the seriatim inputs when supplied; a mixed or
    # unlabelled run aggregates under "ALL".
    legal_entity, segment, cohort_id = _aggregate_labels(inputs.policies)

    result = ReserveResult(
        metadata=ResultMetadata(
            valuation_date=valuation_date,
            framework=Framework.BEL,
            methodology_version=METHODOLOGY_VERSION,
            run_id=inputs.run_id,
            assumption_set_id=inputs.assumption_set.assumption_set_id,
        ),
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        gross_reserve=gross_bel,
        ceded_reserve=0.0,  # Phase 1: reinsurance not yet applied
        net_reserve=gross_bel,
        components={
            "policy_bel": policy_bel,
            "policy_count": len(policy_bel),
            "total_outflows_undiscounted": total_outflows_undiscounted,
            "risk_free_curve": bel_config.risk_free_curve.value,
            "curve_interpolation": bel_config.curve_interpolation.value,
        },
    )
    return BelOutput(reserve_result=result)


def _aggregate_labels(policies: list[MygaPolicyState]) -> tuple[str, str, str]:
    """Single (legal_entity, segment, cohort_id) label set for the aggregate result."""
    if not policies:
        return "ALL", "ALL", "ALL"

    def collapse(values: set[str]) -> str:
        return values.pop() if len(values) == 1 else "ALL"

    return (
        collapse({p.legal_entity for p in policies}),
        collapse({p.segment for p in policies}),
        collapse({p.cohort_id for p in policies}),
    )

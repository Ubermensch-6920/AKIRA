"""
VM-22 (STAT) reserve calculation.

Computes the deterministic reserve (DR) and stochastic reserve (SR)
under VM-22, returning the configured component (DR-only or max(DR, SR))
at the configured CTE level.

Method (Phase 1):
  DR — present value of projected best-estimate liability outflows
    (death + surrender + partial withdrawal + maturity benefits, paid at
    period end) discounted on the supplied valuation curve. This is the
    single deterministic path of the best-estimate projection.
  SR — CTE(level) of scenario reserves, where each scenario re-discounts
    the same outflows on a parallel-shifted curve. The shock set below is
    a deterministic placeholder standing in for the NAIC scenario
    generator (ASSUMPTION REQUIRED: replace with the prescribed generator
    output once the scenario feed exists). CTE(x) = average of the worst
    (highest-reserve) (1 - x) fraction of scenarios.

Phase 1 simplifications (documented for review):
  - Liability cash flows are not re-projected per scenario: only the
    discounting changes. Dynamic lapse / crediting interaction with the
    rate path is deferred until an interest-rate path reaches the MYGA
    engine (MVA is currently hard-zero there for the same reason).
  - ``use_prescribed_margins`` is not yet applied — the best-estimate
    projection basis carries no explicit margins.
  - Shocked zero rates are floored at 0%.
"""

import math
from datetime import date

from pydantic import BaseModel

from ..assumptions.enums import CTELevel, CurveInterpolation, Framework, Vm22Component
from ..assumptions.sets import AssumptionSet
from ..core.discount import CurvePoint, DiscountCurve
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult, ResultMetadata
from .bel import _aggregate_labels, _discount_outflows

METHODOLOGY_VERSION = "stat_vm22_v0.1.0"

# Placeholder scenario set: parallel zero-curve shifts (decimal). Stands in
# for the NAIC generator until the prescribed scenario feed is wired.
_SCENARIO_SHIFTS = (
    -0.0200,
    -0.0150,
    -0.0100,
    -0.0075,
    -0.0050,
    -0.0025,
    0.0000,
    0.0025,
    0.0050,
    0.0075,
    0.0100,
    0.0150,
    0.0200,
)

_CTE_FRACTION = {
    CTELevel.CTE65: 0.65,
    CTELevel.CTE70: 0.70,
    CTELevel.CTE80: 0.80,
}


class StatVm22Input(BaseModel):
    """Inputs to the STAT (VM-22) reserve calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    ceded_cash_flows: GrossCashFlows | None = None  # from reinsurance.application
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None
    curve_points: list[CurvePoint] = []  # valuation curve for discounting
    run_id: str = ""


class StatVm22Output(BaseModel):
    """Output of the STAT (VM-22) reserve calculation."""

    reserve_result: ReserveResult


def calculate(inputs: StatVm22Input) -> StatVm22Output:
    """Compute VM-22 reserves (DR + SR per configuration).

    Raises:
        ValueError: If ``gross_cash_flows`` or ``curve_points`` are missing.
    """
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "StatVm22Input.gross_cash_flows is required — run the "
            "projection engine (core.seriatim) first."
        )
    if not inputs.curve_points:
        raise ValueError("StatVm22Input.curve_points is required for discounting.")

    config = inputs.assumption_set.stat_vm22
    valuation_date = inputs.valuation_date or inputs.gross_cash_flows.valuation_date

    # ── Deterministic Reserve ────────────────────────────────────────────
    base_curve = _shifted_curve(inputs.curve_points, 0.0, valuation_date)
    policy_dr, _ = _discount_outflows(inputs.gross_cash_flows, base_curve, valuation_date)
    dr = sum(policy_dr.values())

    # ── Stochastic Reserve: CTE over the scenario shock set ─────────────
    scenario_reserves = []
    for shift in _SCENARIO_SHIFTS:
        curve = _shifted_curve(inputs.curve_points, shift, valuation_date)
        policy_pv, _ = _discount_outflows(inputs.gross_cash_flows, curve, valuation_date)
        scenario_reserves.append(sum(policy_pv.values()))
    sr = _cte(scenario_reserves, _CTE_FRACTION[config.cte_level])

    if config.reserve_component is Vm22Component.DR_ONLY:
        gross_reserve = dr
    else:  # DR_SR_MAX
        gross_reserve = max(dr, sr)

    # ── Ceded: same component rule applied to the ceded stream ──────────
    ceded_reserve = 0.0
    if inputs.ceded_cash_flows is not None:
        policy_ceded_dr, _ = _discount_outflows(
            inputs.ceded_cash_flows, base_curve, valuation_date
        )
        ceded_dr = sum(policy_ceded_dr.values())
        ceded_scenarios = []
        for shift in _SCENARIO_SHIFTS:
            curve = _shifted_curve(inputs.curve_points, shift, valuation_date)
            policy_pv, _ = _discount_outflows(inputs.ceded_cash_flows, curve, valuation_date)
            ceded_scenarios.append(sum(policy_pv.values()))
        ceded_sr = _cte(ceded_scenarios, _CTE_FRACTION[config.cte_level])
        if config.reserve_component is Vm22Component.DR_ONLY:
            ceded_reserve = ceded_dr
        else:
            ceded_reserve = max(ceded_dr, ceded_sr)

    legal_entity, segment, cohort_id = _aggregate_labels(inputs.policies)

    result = ReserveResult(
        metadata=ResultMetadata(
            valuation_date=valuation_date,
            framework=Framework.STAT_VM22,
            methodology_version=METHODOLOGY_VERSION,
            run_id=inputs.run_id,
            assumption_set_id=inputs.assumption_set.assumption_set_id,
        ),
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        gross_reserve=gross_reserve,
        ceded_reserve=ceded_reserve,
        net_reserve=gross_reserve - ceded_reserve,
        components={
            "deterministic_reserve": dr,
            "stochastic_reserve": sr,
            "reserve_component": config.reserve_component.value,
            "cte_level": config.cte_level.value,
            "scenario_set": config.scenario_set.value,
            "scenario_count": len(_SCENARIO_SHIFTS),
            "scenario_reserves": scenario_reserves,
            "policy_dr": policy_dr,
        },
    )
    return StatVm22Output(reserve_result=result)


def _shifted_curve(
    curve_points: list[CurvePoint], shift: float, valuation_date: date
) -> DiscountCurve:
    """Valuation curve with a parallel shift applied (rates floored at 0%)."""
    points = sorted(curve_points, key=lambda p: p.tenor_years)
    return DiscountCurve(
        valuation_date=valuation_date,
        tenors_years=[p.tenor_years for p in points],
        zero_rates=[max(p.rate + shift, 0.0) for p in points],
        interpolation=CurveInterpolation.LINEAR,
    )


def _cte(values: list[float], level: float) -> float:
    """Conditional Tail Expectation: mean of the worst (1 - level) tail.

    "Worst" for a reserve distribution means the highest reserves.
    """
    if not values:
        return 0.0
    ordered = sorted(values, reverse=True)
    # The 1e-9 guard stops float noise (10 × 0.3 → 3.0000000000000004) from
    # ceiling one extra scenario into the tail.
    tail_count = max(1, math.ceil(len(ordered) * (1.0 - level) - 1e-9))
    tail = ordered[:tail_count]
    return sum(tail) / len(tail)

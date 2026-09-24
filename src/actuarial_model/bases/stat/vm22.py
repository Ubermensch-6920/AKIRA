"""
STAT — VM-22 reserve (DR + SR).

Projected on the ``stat.vm22`` assumption block (prudent-estimate decrements
belong there — the engine projects each basis on its own block).

Method (Phase 1):
  DR — present value of projected liability outflows (death + surrender +
    partial withdrawal + maturity, paid at period end) discounted on the
    supplied valuation curve.
  SR — CTE(level) of scenario reserves, where each scenario re-discounts the
    same outflows on a parallel-shifted curve. The shock set below is a
    deterministic placeholder standing in for the NAIC scenario generator
    (ASSUMPTION REQUIRED: replace with the prescribed generator output once
    the scenario feed exists). CTE(x) = average of the worst
    (highest-reserve) (1 - x) fraction of scenarios.
  Reported reserve = DR (DR_ONLY) or max(DR, SR) (DR_SR_MAX); ceded applies
  the same rule to the ceded stream.

Per-policy detail: SR is a portfolio tail statistic, so policy reserves are
the policy DRs scaled pro rata to the reported total.

Phase 1 simplifications (documented for review):
  - Liability cash flows are not re-projected per scenario: only the
    discounting changes (dynamic lapse / MVA need a rate path in the engine).
  - ``use_prescribed_margins`` is not yet applied as a switch.
  - Shocked zero rates are floored at 0%.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import polars as pl

from ...assumptions.enums import CTELevel, Framework, Vm22Component
from ...assumptions.sets import StatVm22Config
from ...engine.curves import CurvePoint, build_curve
from ...engine.projection import Projection
from ..common import (
    MeasureResult,
    RunStamp,
    allocate,
    policy_detail,
    pv_by_policy,
    require_curve,
    reserve_result,
)

METHODOLOGY_VERSION = "stat_vm22_v1.0.0"

# Placeholder scenario set: parallel zero-curve shifts (decimal). Stands in
# for the NAIC generator until the prescribed scenario feed is wired.
SCENARIO_SHIFTS = (
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


def cte(values: Sequence[float], level: float) -> float:
    """Conditional Tail Expectation: mean of the worst (1 - level) tail.

    "Worst" for a reserve distribution means the highest reserves.
    """
    if not values:
        return 0.0
    ordered = sorted(values, reverse=True)
    # The 1e-9 guard stops float noise (10 x 0.3 → 3.0000000000000004) from
    # ceiling one extra scenario into the tail.
    tail_count = max(1, math.ceil(len(ordered) * (1.0 - level) - 1e-9))
    tail = ordered[:tail_count]
    return sum(tail) / len(tail)


def _reserve(
    projection: Projection,
    curve_points: Sequence[CurvePoint],
    config: StatVm22Config,
) -> tuple[pl.DataFrame, float, float, list[float]]:
    """(per-policy DR, DR, SR, scenario reserves) for one stream."""
    policy_dr = pv_by_policy(projection, build_curve(curve_points, floor=0.0))
    dr = float(policy_dr["pv"].sum())
    scenarios = [
        float(pv_by_policy(projection, build_curve(curve_points, shift=s, floor=0.0))["pv"].sum())
        for s in SCENARIO_SHIFTS
    ]
    return policy_dr, dr, cte(scenarios, _CTE_FRACTION[config.cte_level]), scenarios


def _component(config: StatVm22Config, dr: float, sr: float) -> float:
    return dr if config.reserve_component is Vm22Component.DR_ONLY else max(dr, sr)


def calculate(
    gross: Projection,
    ceded: Projection | None,
    config: StatVm22Config,
    curve_points: Sequence[CurvePoint],
    stamp: RunStamp,
) -> MeasureResult:
    """VM-22 reserve per configuration.

    Raises:
        ValueError: If ``curve_points`` is empty.
    """
    require_curve(curve_points, "VM-22")

    policy_dr, dr, sr, scenario_reserves = _reserve(gross, curve_points, config)
    gross_reserve = _component(config, dr, sr)

    policy_ceded_dr = None
    ceded_reserve = 0.0
    if ceded is not None:
        policy_ceded_dr, ceded_dr, ceded_sr, _ = _reserve(ceded, curve_points, config)
        ceded_reserve = _component(config, ceded_dr, ceded_sr)

    detail = allocate(
        policy_detail(gross.labels(), policy_dr, policy_ceded_dr), gross_reserve, ceded_reserve
    )
    result = reserve_result(
        stamp,
        Framework.STAT_VM22,
        METHODOLOGY_VERSION,
        detail,
        {
            "deterministic_reserve": dr,
            "stochastic_reserve": sr,
            "reserve_component": config.reserve_component.value,
            "cte_level": config.cte_level.value,
            "scenario_set": config.scenario_set.value,
            "scenario_count": len(SCENARIO_SHIFTS),
            "scenario_reserves": scenario_reserves,
            "allocation": "pro_rata_deterministic_reserve",
        },
        gross=gross_reserve,
        ceded=ceded_reserve,
    )
    return MeasureResult(reserve_result=result, policy_detail=detail)

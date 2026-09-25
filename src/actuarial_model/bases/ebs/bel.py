"""
EBS — Best Estimate Liability (risk-free).

BEL = best-estimate liability outflows (death + surrender + partial
withdrawal + maturity benefits, paid at period end) discounted on the
configured risk-free curve. Projected on the ``ebs.bel`` assumption block.
It is the economic starting point of the EBS technical provisions (which
add the illiquidity premium and risk margin) and the management-view
comparator for the other bases.

Ceded BEL discounts the ceded stream on the same curve; net = gross - ceded.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...assumptions.enums import Framework
from ...assumptions.sets import BelConfig
from ...engine.curves import CurvePoint, build_curve
from ...engine.projection import Projection
from ..common import (
    MeasureResult,
    RunStamp,
    policy_detail,
    pv_by_policy,
    require_curve,
    reserve_result,
    total_outflows,
)

METHODOLOGY_VERSION = "bel_v1.0.0"


def calculate(
    gross: Projection,
    ceded: Projection | None,
    config: BelConfig,
    curve_points: Sequence[CurvePoint],
    stamp: RunStamp,
) -> MeasureResult:
    """Risk-free BEL per policy and in total.

    Raises:
        ValueError: If ``curve_points`` is empty.
    """
    require_curve(curve_points, "BEL")
    curve = build_curve(curve_points, interpolation=config.curve_interpolation)

    detail = policy_detail(
        gross.labels(),
        pv_by_policy(gross, curve),
        pv_by_policy(ceded, curve) if ceded is not None else None,
    )
    result = reserve_result(
        stamp,
        Framework.BEL,
        METHODOLOGY_VERSION,
        detail,
        {
            "total_outflows_undiscounted": total_outflows(gross),
            "risk_free_curve": config.risk_free_curve.value,
            "curve_interpolation": config.curve_interpolation.value,
            "projection_methodology": gross.methodology_version,
        },
    )
    return MeasureResult(reserve_result=result, policy_detail=detail)

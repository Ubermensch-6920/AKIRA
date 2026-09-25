"""
LDTI — ASC 944 Liability for Future Policy Benefits (LFPB).

Projected on the ``ldti`` assumption block, discounted on the upper-medium-
grade (single-A) curve.

Method (Phase 1, single-premium MYGA):
  NPR-mechanics collapse for a single-premium contract: there are no future
  premiums after issue, so LFPB = PV of future benefit outflows at the
  discount curve. The net premium ratio is still computed and capped
  (NPR = min(PV benefits / premium, cap)) and reported for disclosure, but
  with zero future premiums it does not alter the liability.

Phase 1 simplifications (documented for review):
  - ``cohort_granularity`` is not applied — each run is one cohort.
  - NPR is computed from the valuation-date projection, not locked at issue.
  - The supplied ``curve_points`` are taken as the discount-source curve
    (``discount_source`` is a label; no live market feed exists yet).
"""

from __future__ import annotations

from collections.abc import Sequence

from ...assumptions.enums import Framework
from ...assumptions.sets import LdtiConfig
from ...engine.curves import CurvePoint, build_curve
from ...engine.projection import Projection
from ...models.policy import MygaPolicyState
from ..common import (
    MeasureResult,
    RunStamp,
    policy_detail,
    pv_by_policy,
    require_curve,
    reserve_result,
)

METHODOLOGY_VERSION = "ldti_lfpb_v1.0.0"


def calculate(
    gross: Projection,
    ceded: Projection | None,
    policies: Sequence[MygaPolicyState],
    config: LdtiConfig,
    curve_points: Sequence[CurvePoint],
    stamp: RunStamp,
) -> MeasureResult:
    """LFPB per policy and in total, with the (capped) net premium ratio.

    Raises:
        ValueError: If ``curve_points`` is empty.
    """
    require_curve(curve_points, "LDTI")
    curve = build_curve(curve_points, floor=0.0)

    detail = policy_detail(
        gross.labels(),
        pv_by_policy(gross, curve),
        pv_by_policy(ceded, curve) if ceded is not None else None,
    )
    gross_lfpb = float(detail["gross"].sum())
    total_premium = sum(p.single_premium for p in policies)
    raw_npr = gross_lfpb / total_premium if total_premium > 0.0 else None
    net_premium_ratio = min(raw_npr, config.net_premium_ratio_cap) if raw_npr is not None else None

    result = reserve_result(
        stamp,
        Framework.LDTI,
        METHODOLOGY_VERSION,
        detail,
        {
            "component": "LFPB",
            "net_premium_ratio": net_premium_ratio,
            "net_premium_ratio_uncapped": raw_npr,
            "net_premium_ratio_cap": config.net_premium_ratio_cap,
            "discount_source": config.discount_source.value,
        },
    )
    return MeasureResult(reserve_result=result, policy_detail=detail)

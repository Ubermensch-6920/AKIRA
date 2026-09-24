"""
Yield curves and discount factors, built on gaspatchio's ``Curve``.

Conventions (unchanged from the pre-gaspatchio engine):
  - Zero rates are annual-effective decimals (0.04 == 4%).
  - DF(t) = (1 + r(t)) ** -t with t in years from the valuation date.
  - Tenors outside the supplied knots use the nearest endpoint rate (flat
    extrapolation) — gaspatchio's ``extrapolation="flat"``.

Every basis discounts on its own curve: STAT VM-22 on the valuation curve
(plus scenario shifts), LDTI on the upper-medium-grade curve, US GAAP fair
value on the discount-basis curve, EBS on risk-free (+ illiquidity premium).
:func:`build_curve` covers all of them via ``shift`` / ``floor``.
"""

from __future__ import annotations

from collections.abc import Sequence

from gaspatchio.curves import Curve
from pydantic import BaseModel

from ..assumptions.enums import CurveInterpolation

_GASPATCHIO_INTERPOLATION = {
    CurveInterpolation.LINEAR: "linear",
    CurveInterpolation.LOG_LINEAR: "log_linear",
    CurveInterpolation.PCHIP: "pchip",
}


class CurvePoint(BaseModel):
    """A single point on a zero curve."""

    tenor_years: float
    rate: float  # decimal, e.g. 0.04 == 4 %


def build_curve(
    curve_points: Sequence[CurvePoint],
    *,
    interpolation: CurveInterpolation = CurveInterpolation.LINEAR,
    shift: float = 0.0,
    floor: float | None = None,
) -> Curve:
    """Build a gaspatchio ``Curve`` from raw zero-rate knots.

    Args:
        curve_points: Knots in any order; tenors must be unique.
        interpolation: Rate interpolation between knots.
        shift: Parallel shift (decimal) added to every knot — basis spreads,
            illiquidity premium, own-credit, VM-22 rate scenarios.
        floor: Optional lower bound applied to each shifted knot rate.

    Raises:
        ValueError: If no points are supplied or tenors are duplicated.
    """
    if not curve_points:
        raise ValueError(
            "curve_points must be supplied — there is no live market-data feed yet."
        )
    points = sorted(curve_points, key=lambda p: p.tenor_years)
    tenors = [p.tenor_years for p in points]
    if len(set(tenors)) != len(tenors):
        raise ValueError("Curve tenors must not contain duplicates.")

    rates = [p.rate + shift for p in points]
    if floor is not None:
        rates = [max(r, floor) for r in rates]

    # gaspatchio needs two knots; a single-point curve is flat at that rate.
    if len(tenors) == 1:
        tenors = [tenors[0], tenors[0] + 1.0]
        rates = [rates[0], rates[0]]

    return Curve.from_zero_rates(
        tenors=tenors,
        rates=rates,
        interpolation=_GASPATCHIO_INTERPOLATION[interpolation],  # type: ignore[arg-type]
        extrapolation="flat",
    )


def discount_factors(curve: Curve, tenors_years: Sequence[float]) -> list[float]:
    """Discount factors at ``tenors_years``; tenors <= 0 discount to 1.0."""
    clipped = [max(float(t), 0.0) for t in tenors_years]
    factors = curve.discount_factor(clipped)
    return [1.0 if t <= 0.0 else float(df) for t, df in zip(clipped, factors, strict=True)]  # type: ignore[arg-type]

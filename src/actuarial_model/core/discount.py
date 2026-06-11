"""
Yield curves and discount-factor utilities.

Builds discount factors from a configured :class:`RiskFreeCurve` source
according to :class:`CurveInterpolation` rules, and exposes helpers to
discount cash-flow arrays carrying explicit ``pd.DatetimeIndex`` labels.

Conventions:
  - Zero rates are annual-effective decimals (0.04 == 4%).
  - DF(t) = (1 + r(t)) ** -t  with t in years from the valuation date.
  - Tenors outside the supplied curve range use the nearest endpoint rate
    (flat extrapolation) under both interpolation methods.
"""

from datetime import date

import numpy as np
from pydantic import BaseModel, model_validator

from ..assumptions.enums import CurveInterpolation, RiskFreeCurve


class CurvePoint(BaseModel):
    """A single point on a yield curve."""

    tenor_years: float
    rate: float  # decimal, e.g. 0.04 == 4 %


class DiscountInput(BaseModel):
    """Inputs to discount-factor construction."""

    valuation_date: date
    curve: RiskFreeCurve
    interpolation: CurveInterpolation
    curve_points: list[CurvePoint] = []


class DiscountOutput(BaseModel):
    """Discount factor curve as paired tenor / DF arrays."""

    tenors_years: list[float] = []
    discount_factors: list[float] = []


class DiscountCurve(BaseModel):
    """An interpolatable zero curve anchored at a valuation date.

    Use :func:`build_curve` to construct one from a :class:`DiscountInput`.
    """

    valuation_date: date
    tenors_years: list[float]
    zero_rates: list[float]
    interpolation: CurveInterpolation = CurveInterpolation.LINEAR

    @model_validator(mode="after")
    def _validate_curve(self) -> "DiscountCurve":
        if not self.tenors_years:
            raise ValueError("Curve must have at least one point.")
        if len(self.tenors_years) != len(self.zero_rates):
            raise ValueError("tenors_years and zero_rates must be the same length.")
        if sorted(self.tenors_years) != list(self.tenors_years):
            raise ValueError("tenors_years must be sorted ascending.")
        if len(set(self.tenors_years)) != len(self.tenors_years):
            raise ValueError("tenors_years must not contain duplicates.")
        return self

    def zero_rate(self, tenor_years: float) -> float:
        """Interpolated annual-effective zero rate at the given tenor.

        Tenors beyond the curve ends use the endpoint rate (flat extrapolation).
        """
        tenors = np.asarray(self.tenors_years)
        rates = np.asarray(self.zero_rates)

        if len(tenors) == 1:
            return float(rates[0])

        t = float(np.clip(tenor_years, tenors[0], tenors[-1]))

        if self.interpolation is CurveInterpolation.CUBIC_SPLINE:
            from scipy.interpolate import CubicSpline

            spline = CubicSpline(tenors, rates)
            return float(spline(t))

        return float(np.interp(t, tenors, rates))

    def discount_factor(self, tenor_years: float) -> float:
        """DF(t) = (1 + r(t)) ** -t. Tenors <= 0 return 1.0."""
        if tenor_years <= 0.0:
            return 1.0
        rate = self.zero_rate(tenor_years)
        return float((1.0 + rate) ** -tenor_years)

    def discount_factor_for_date(self, cash_flow_date: date) -> float:
        """Discount factor for a cash flow paid on ``cash_flow_date``."""
        tenor = (cash_flow_date - self.valuation_date).days / 365.25
        return self.discount_factor(tenor)


def build_curve(inputs: DiscountInput) -> DiscountCurve:
    """Construct an interpolatable :class:`DiscountCurve` from raw curve points."""
    if not inputs.curve_points:
        raise ValueError(
            "DiscountInput.curve_points must be supplied — there is no live "
            f"market-data feed for {inputs.curve.value} in Phase 1."
        )
    points = sorted(inputs.curve_points, key=lambda p: p.tenor_years)
    return DiscountCurve(
        valuation_date=inputs.valuation_date,
        tenors_years=[p.tenor_years for p in points],
        zero_rates=[p.rate for p in points],
        interpolation=inputs.interpolation,
    )


def calculate(inputs: DiscountInput) -> DiscountOutput:
    """Build a discount-factor curve on a monthly tenor grid.

    The grid runs from one month out to the longest supplied tenor, so
    downstream consumers can index it directly by projection period.
    """
    curve = build_curve(inputs)

    max_tenor = curve.tenors_years[-1]
    n_months = max(round(max_tenor * 12), 1)
    grid = [month / 12.0 for month in range(1, n_months + 1)]

    return DiscountOutput(
        tenors_years=grid,
        discount_factors=[curve.discount_factor(t) for t in grid],
    )

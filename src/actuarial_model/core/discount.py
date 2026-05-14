"""
Yield curves and discount-factor utilities.

Builds discount factors from a configured :class:`RiskFreeCurve` source
according to :class:`CurveInterpolation` rules, and exposes helpers to
discount cash-flow arrays carrying explicit ``pd.DatetimeIndex`` labels.
"""

from datetime import date

from pydantic import BaseModel

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


def calculate(inputs: DiscountInput) -> DiscountOutput:
    """Build a discount-factor curve from configured inputs.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

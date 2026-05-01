"""
Yield curves and discount-factor utilities.

Builds discount factors from a configured :class:`RiskFreeCurve` source
according to :class:`CurveInterpolation` rules, and exposes helpers to
discount cash-flow arrays carrying explicit ``pd.DatetimeIndex`` labels.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.enums import CurveInterpolation, RiskFreeCurve


class DiscountInput(BaseModel):
    """Inputs to discount-factor construction."""

    valuation_date: date
    curve: RiskFreeCurve
    interpolation: CurveInterpolation
    # ASSUMPTION REQUIRED: raw curve points / source contract


class DiscountOutput(BaseModel):
    """Discount factor curve as paired tenor / DF arrays."""

    # ASSUMPTION REQUIRED: numpy array container pending wiring
    tenors_years: list[float] = []
    discount_factors: list[float] = []


def calculate(inputs: DiscountInput) -> DiscountOutput:
    """Build a discount-factor curve from configured inputs.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

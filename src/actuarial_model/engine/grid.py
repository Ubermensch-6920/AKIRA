"""
The shared monthly projection grid.

Every policy is projected from the valuation date on the same monthly grid,
so period dates and payment tenors are grid-level vectors computed once and
broadcast to every policy row of the gaspatchio frame. Period ``t``
(0-based) runs from ``valuation_date + t months`` to ``valuation_date +
(t + 1) months``; benefits are paid at period end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import polars as pl
from dateutil.relativedelta import relativedelta

DAYS_PER_YEAR = 365.25  # year-fraction convention for tenors and improvement


def add_months(anchor: date, months: int) -> date:
    """``anchor`` shifted by ``months`` calendar months (day clamped to month end)."""
    return anchor + relativedelta(months=months)


def months_between(start: date, end: date) -> int:
    """Whole calendar months from ``start`` to ``end`` (day of month ignored)."""
    return (end.year - start.year) * 12 + (end.month - start.month)


def year_fraction(start: date, end: date) -> float:
    """Actual / 365.25 year fraction."""
    return (end - start).days / DAYS_PER_YEAR


@dataclass(frozen=True)
class ProjectionGrid:
    """Monthly projection grid anchored at the valuation date."""

    valuation_date: date
    n_periods: int
    period_start_dates: list[date] = field(init=False, repr=False)
    period_end_dates: list[date] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.n_periods <= 0:
            raise ValueError("n_periods must be positive.")
        starts = [add_months(self.valuation_date, t) for t in range(self.n_periods)]
        ends = [add_months(self.valuation_date, t + 1) for t in range(self.n_periods)]
        object.__setattr__(self, "period_start_dates", starts)
        object.__setattr__(self, "period_end_dates", ends)

    @classmethod
    def from_horizon(cls, valuation_date: date, horizon_years: int) -> ProjectionGrid:
        return cls(valuation_date=valuation_date, n_periods=horizon_years * 12)

    @property
    def period_index(self) -> list[int]:
        return list(range(self.n_periods))

    @property
    def payment_tenors(self) -> list[float]:
        """Years from valuation to each period end — the discounting tenor."""
        return [year_fraction(self.valuation_date, d) for d in self.period_end_dates]

    def years_since(self, base: date) -> list[float]:
        """Years from ``base`` to each period start (mortality improvement clock)."""
        return [year_fraction(base, d) for d in self.period_start_dates]

    def days_from_valuation(self) -> list[float]:
        """Days from valuation to each period start."""
        return [float((d - self.valuation_date).days) for d in self.period_start_dates]


def grid_vector(values: list[float] | list[int], dtype: pl.DataType) -> pl.Expr:
    """A single grid-level list broadcast to every row of a frame."""
    return pl.lit(pl.Series([values], dtype=pl.List(dtype))).first()

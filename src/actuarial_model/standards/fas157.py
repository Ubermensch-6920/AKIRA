"""
ASC 820 fair-value liability calculation (formerly FAS 157).

Computes a fair-value liability with explicit risk margin (cost-of-
capital, CALM, or explicit), non-performance / own-credit risk
adjustment, and a configured discount basis.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult


class Fas157Input(BaseModel):
    """Inputs to the ASC 820 fair-value calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None
    measurement_date: date | None = None  # ASC 820 measurement date (may differ from valuation_date)


class Fas157Output(BaseModel):
    """Output of the ASC 820 fair-value calculation."""

    reserve_result: ReserveResult


def calculate(inputs: Fas157Input) -> Fas157Output:
    """Compute ASC 820 fair-value liability.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

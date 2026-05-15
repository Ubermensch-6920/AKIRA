"""
Best Estimate Liability calculation module.

BEL = sum of best-estimate liability cash flows discounted at the
risk-free curve. Cross-cutting input to EBS, FAS 157, and serves as a
management-view comparator for STAT and LDTI.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..core.discount import CurvePoint
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult


class BelInput(BaseModel):
    """Inputs to the BEL calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None
    curve_points: list[CurvePoint] = []  # raw yield curve data for discounting


class BelOutput(BaseModel):
    """Output of the BEL calculation."""

    reserve_result: ReserveResult


def calculate(inputs: BelInput) -> BelOutput:
    """Compute Best Estimate Liability per the configured BEL config.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

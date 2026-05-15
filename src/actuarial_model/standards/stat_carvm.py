"""
Pre-VM-22 CARVM (STAT) reserve calculation.

Implements Commissioner's Annuity Reserve Valuation Method per the
configured Actuarial Guideline (AG33 / AG35) with cash-flow-testing
overlay scenarios (Reg 126 or company).
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult


class StatCarvmInput(BaseModel):
    """Inputs to the STAT (CARVM) reserve calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None


class StatCarvmOutput(BaseModel):
    """Output of the STAT (CARVM) reserve calculation."""

    reserve_result: ReserveResult


def calculate(inputs: StatCarvmInput) -> StatCarvmOutput:
    """Compute Pre-VM-22 CARVM reserves.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

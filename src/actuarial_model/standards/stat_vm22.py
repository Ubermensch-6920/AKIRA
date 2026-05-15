"""
VM-22 (STAT) reserve calculation.

Computes the deterministic reserve (DR) and stochastic reserve (SR)
under VM-22, returning the configured component (DR-only or max(DR, SR))
at the configured CTE level.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult


class StatVm22Input(BaseModel):
    """Inputs to the STAT (VM-22) reserve calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None


class StatVm22Output(BaseModel):
    """Output of the STAT (VM-22) reserve calculation."""

    reserve_result: ReserveResult


def calculate(inputs: StatVm22Input) -> StatVm22Output:
    """Compute VM-22 reserves (DR + SR per configuration).

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

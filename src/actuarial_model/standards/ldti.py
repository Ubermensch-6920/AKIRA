"""
ASC 944 Long-Duration Targeted Improvements (LDTI) reserve calculation.

Computes the Liability for Future Policy Benefits (LFPB) using a net
premium ratio capped per configuration, plus the Deferred Acquisition
Cost (DAC) balance amortized on a straight-line basis (post-LDTI) or an
EGP basis (legacy).
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult


class LdtiInput(BaseModel):
    """Inputs to the LDTI calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None
    transition_date: date | None = None  # ASC 944 entity-level transition date


class LdtiOutput(BaseModel):
    """Output of the LDTI calculation: LFPB and DAC results."""

    lfpb_result: ReserveResult
    dac_result: ReserveResult


def calculate(inputs: LdtiInput) -> LdtiOutput:
    """Compute LDTI LFPB and DAC.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

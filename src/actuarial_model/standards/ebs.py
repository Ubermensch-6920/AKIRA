"""
Bermuda Economic Balance Sheet (EBS) calculation.

Computes Technical Provisions (Standard or Scenario-Based Approach),
risk margin, and BSCR-style stresses (lapse, mortality improvement).
"""

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.results import ReserveResult


class EbsInput(BaseModel):
    """Inputs to the EBS calculation."""

    assumption_set: AssumptionSet
    # ASSUMPTION REQUIRED: full input contract pending product spec


class EbsOutput(BaseModel):
    """Output of the EBS calculation."""

    technical_provisions: ReserveResult
    risk_margin: ReserveResult


def calculate(inputs: EbsInput) -> EbsOutput:
    """Compute EBS technical provisions and risk margin.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

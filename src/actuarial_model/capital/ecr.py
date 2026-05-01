"""
Bermuda Enhanced Capital Requirement (ECR) calculation.

Computes BSCR via the Standard Formula (or partial / full internal
model) over EBS-basis assets and liabilities.
"""

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.results import CapitalResult


class EcrInput(BaseModel):
    """Inputs to the Bermuda ECR calculation."""

    assumption_set: AssumptionSet
    # ASSUMPTION REQUIRED: full input contract pending product spec


class EcrOutput(BaseModel):
    """Output of the Bermuda ECR calculation."""

    capital_result: CapitalResult


def calculate(inputs: EcrInput) -> EcrOutput:
    """Compute Bermuda ECR.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

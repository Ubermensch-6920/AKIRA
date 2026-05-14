"""
Bermuda Enhanced Capital Requirement (ECR) calculation.

Computes BSCR via the Standard Formula (or partial / full internal
model) over EBS-basis assets and liabilities.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.asset import AssetRecord
from ..models.results import CapitalResult, ReserveResult


class EcrInput(BaseModel):
    """Inputs to the Bermuda ECR calculation."""

    assumption_set: AssumptionSet
    reserve_results: list[ReserveResult] = []
    assets: list[AssetRecord] = []
    valuation_date: date | None = None


class EcrOutput(BaseModel):
    """Output of the Bermuda ECR calculation."""

    capital_result: CapitalResult


def calculate(inputs: EcrInput) -> EcrOutput:
    """Compute Bermuda ECR.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

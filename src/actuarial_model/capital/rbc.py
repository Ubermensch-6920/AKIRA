"""
NAIC Risk-Based Capital (RBC) calculation.

Aggregates C-1 (asset), C-2 (insurance), C-3 (interest-rate), and C-4
(business) risk components into Total Adjusted Capital and the
Authorized Control Level (ACL) RBC ratio.
"""

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.results import CapitalResult


class RbcInput(BaseModel):
    """Inputs to the NAIC RBC calculation."""

    assumption_set: AssumptionSet
    # ASSUMPTION REQUIRED: full input contract pending product spec


class RbcOutput(BaseModel):
    """Output of the NAIC RBC calculation."""

    capital_result: CapitalResult


def calculate(inputs: RbcInput) -> RbcOutput:
    """Compute NAIC RBC.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

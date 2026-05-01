"""
Best Estimate Liability calculation module.

BEL = sum of best-estimate liability cash flows discounted at the
risk-free curve. Cross-cutting input to EBS, FAS 157, and serves as a
management-view comparator for STAT and LDTI.
"""

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.results import ReserveResult


class BelInput(BaseModel):
    """Inputs to the BEL calculation."""

    assumption_set: AssumptionSet
    # ASSUMPTION REQUIRED: full input contract pending product spec


class BelOutput(BaseModel):
    """Output of the BEL calculation."""

    reserve_result: ReserveResult


def calculate(inputs: BelInput) -> BelOutput:
    """Compute Best Estimate Liability per the configured BEL config.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

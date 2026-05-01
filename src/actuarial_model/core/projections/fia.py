"""
FIA projection engine (Phase 2 stub).

Will project Fixed Indexed Annuity cash flows including index-credit
mechanics, embedded option costs, and rider liabilities.
"""

from pydantic import BaseModel

from ...assumptions.sets import AssumptionSet
from ...models.policy import FiaPolicyState


class FiaProjectionInput(BaseModel):
    """Inputs to the FIA projection engine."""

    assumption_set: AssumptionSet
    policies: list[FiaPolicyState]


class FiaProjectionOutput(BaseModel):
    """FIA gross per-policy cash flow streams."""

    cash_flows: dict = {}


def calculate(inputs: FiaProjectionInput) -> FiaProjectionOutput:
    """Project gross FIA cash flows.

    Raises:
        NotImplementedError: Phase 2 stub — pending product spec.
    """
    raise NotImplementedError("Phase 2 — pending product spec")

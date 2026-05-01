"""
VA projection engine (Phase 3 stub).

Will project Variable Annuity cash flows including separate-account fund
returns, GMxB rider charges and benefits, and dynamic policyholder
behavior.
"""

from pydantic import BaseModel

from ...assumptions.sets import AssumptionSet
from ...models.policy import VaPolicyState


class VaProjectionInput(BaseModel):
    """Inputs to the VA projection engine."""

    assumption_set: AssumptionSet
    policies: list[VaPolicyState]


class VaProjectionOutput(BaseModel):
    """VA gross per-policy cash flow streams."""

    cash_flows: dict = {}


def calculate(inputs: VaProjectionInput) -> VaProjectionOutput:
    """Project gross VA cash flows.

    Raises:
        NotImplementedError: Phase 3 stub — pending product spec.
    """
    raise NotImplementedError("Phase 3 — pending product spec")

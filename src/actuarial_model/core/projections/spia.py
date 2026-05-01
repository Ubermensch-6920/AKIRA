"""
SPIA projection engine (Phase 2 stub).

Will project Single Premium Immediate Annuity cash flows: guaranteed
income payments and survivor / certain-period mortality decrements.
"""

from pydantic import BaseModel

from ...assumptions.sets import AssumptionSet
from ...models.policy import SpiaPolicyState


class SpiaProjectionInput(BaseModel):
    """Inputs to the SPIA projection engine."""

    assumption_set: AssumptionSet
    policies: list[SpiaPolicyState]


class SpiaProjectionOutput(BaseModel):
    """SPIA gross per-policy cash flow streams."""

    cash_flows: dict = {}


def calculate(inputs: SpiaProjectionInput) -> SpiaProjectionOutput:
    """Project gross SPIA cash flows.

    Raises:
        NotImplementedError: Phase 2 stub — pending product spec.
    """
    raise NotImplementedError("Phase 2 — pending product spec")

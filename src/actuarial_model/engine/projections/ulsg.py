"""
ULSG projection engine (Phase 3 stub).

Will project Universal Life with Secondary Guarantee cash flows: COI
charges, account value roll-forward, shadow-account mechanics, and
secondary-guarantee triggers.
"""

from pydantic import BaseModel

from ...assumptions.sets import AssumptionSet
from ...models.policy import UlsgPolicyState


class UlsgProjectionInput(BaseModel):
    """Inputs to the ULSG projection engine."""

    assumption_set: AssumptionSet
    policies: list[UlsgPolicyState]


class UlsgProjectionOutput(BaseModel):
    """ULSG gross per-policy cash flow streams."""

    cash_flows: dict = {}


def calculate(inputs: UlsgProjectionInput) -> UlsgProjectionOutput:
    """Project gross ULSG cash flows.

    Raises:
        NotImplementedError: Phase 3 stub — pending product spec.
    """
    raise NotImplementedError("Phase 3 — pending product spec")

"""
MYGA projection engine (Phase 1).

Projects per-policy MYGA cash flows: account-value roll-forward at the
guaranteed rate, surrender / death decrements, MVA where applicable, and
end-of-guarantee disposition. Outputs the gross cash-flow streams that
feed BEL discounting and every framework reserve module.
"""

from datetime import date

from pydantic import BaseModel

from ...assumptions.sets import AssumptionSet
from ...models.cash_flows import GrossCashFlows
from ...models.policy import MygaPolicyState


class MygaProjectionInput(BaseModel):
    """Inputs to the MYGA projection engine."""

    assumption_set: AssumptionSet
    policies: list[MygaPolicyState]
    valuation_date: date | None = None
    projection_horizon_years: int = 30


class MygaProjectionOutput(BaseModel):
    """MYGA gross per-policy cash flow streams."""

    cash_flows: GrossCashFlows | None = None


def calculate(inputs: MygaProjectionInput) -> MygaProjectionOutput:
    """Project gross MYGA cash flows for every policy in ``inputs.policies``.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

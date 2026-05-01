"""
Risk-transfer testing per ASC 944 / SSAP 61R.

Implements the ``REASONABLE_POSSIBILITY`` test (ASC 944) and the
``ERD`` (Expected Reinsurer Deficit) test, returning whether the treaty
qualifies for reinsurance accounting (vs. deposit accounting).
"""

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.reinsurance import ReinsuranceTreaty


class RiskTransferInput(BaseModel):
    """Inputs to the risk-transfer test."""

    assumption_set: AssumptionSet
    treaty: ReinsuranceTreaty
    # ASSUMPTION REQUIRED: stochastic scenario inputs pending product spec


class RiskTransferOutput(BaseModel):
    """Output of the risk-transfer test."""

    qualifies_for_reinsurance_accounting: bool
    erd_value: float | None = None
    reasonable_possibility_pct: float | None = None
    components: dict = {}


def calculate(inputs: RiskTransferInput) -> RiskTransferOutput:
    """Run the configured risk-transfer test for ``inputs.treaty``.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

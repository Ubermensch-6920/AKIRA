"""
Risk-transfer testing per ASC 944 / SSAP 61R.

Implements the ``REASONABLE_POSSIBILITY`` test (ASC 944) and the
``ERD`` (Expected Reinsurer Deficit) test, returning whether the treaty
qualifies for reinsurance accounting (vs. deposit accounting).
"""

from pydantic import BaseModel, ConfigDict

from ..assumptions.sets import AssumptionSet
from ..engine.projection import Projection
from ..models.reinsurance import ReinsuranceTreaty
from ..models.scenarios import ScenarioPath


class RiskTransferInput(BaseModel):
    """Inputs to the risk-transfer test."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    assumption_set: AssumptionSet
    treaty: ReinsuranceTreaty
    scenario_paths: list[ScenarioPath] = []
    gross_projection: Projection | None = None


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

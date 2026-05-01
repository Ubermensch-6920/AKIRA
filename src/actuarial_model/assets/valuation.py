"""
Framework-specific asset valuation views.

Computes book / amortized, fair-value, and EBS-market views over the
asset ledger. Applies post-haircut adjustments where required by EBS.
"""

from pydantic import BaseModel

from ..assumptions.enums import Framework
from ..assumptions.sets import AssumptionSet
from ..models.asset import AssetRecord


class AssetValuationInput(BaseModel):
    """Inputs to the asset valuation view."""

    assumption_set: AssumptionSet
    framework: Framework
    assets: list[AssetRecord]


class AssetValuationOutput(BaseModel):
    """Output of the asset valuation view: framework-basis values per asset."""

    framework: Framework
    valued_assets: list[AssetRecord]


def calculate(inputs: AssetValuationInput) -> AssetValuationOutput:
    """Produce the asset valuation view for ``inputs.framework``.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

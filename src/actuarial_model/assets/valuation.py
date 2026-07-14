"""
Framework-specific asset valuation views.

Computes book / amortized, fair-value, and EBS-market views over the
asset ledger. Applies post-haircut adjustments where required by EBS.

Carrying-value rules (Phase 1):
  STAT (CARVM / VM-22) and NAIC RBC — book value; non-admitted assets
    carry at zero (excluded from statutory surplus).
  LDTI — amortized cost for HTM positions, market value otherwise.
  FAS 157 / BEL — market value.
  EBS — post-haircut ``market_value_ebs``, falling back to market value
    when no haircut value is recorded.
"""

from pydantic import BaseModel, Field

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
    carrying_values: dict[str, float] = Field(default_factory=dict)
    total_carrying_value: float = 0.0


def calculate(inputs: AssetValuationInput) -> AssetValuationOutput:
    """Produce the asset valuation view for ``inputs.framework``."""
    carrying_values = {
        asset.asset_id: _carrying_value(asset, inputs.framework)
        for asset in inputs.assets
    }
    return AssetValuationOutput(
        framework=inputs.framework,
        valued_assets=list(inputs.assets),
        carrying_values=carrying_values,
        total_carrying_value=sum(carrying_values.values()),
    )


def _carrying_value(asset: AssetRecord, framework: Framework) -> float:
    if framework in (Framework.STAT_CARVM, Framework.STAT_VM22, Framework.NAIC_RBC):
        return asset.book_value if asset.admitted_flag else 0.0
    if framework is Framework.LDTI:
        return (
            asset.amortized_cost
            if asset.gaap_classification == "HTM"
            else asset.market_value
        )
    if framework is Framework.EBS:
        return (
            asset.market_value_ebs
            if asset.market_value_ebs is not None
            else asset.market_value
        )
    # FAS157 / BEL — fair value.
    return asset.market_value

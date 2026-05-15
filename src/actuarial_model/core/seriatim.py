"""
Seriatim dispatcher.

Routes a list of :class:`PolicyStateBase` records to the appropriate
product projection engine based on :attr:`PolicyStateBase.product_type`,
then concatenates the per-product cash flow outputs.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.asset import AssetRecord
from ..models.cash_flows import GrossCashFlows
from ..models.policy import PolicyStateBase


class SeriatimInput(BaseModel):
    """Inputs to the seriatim dispatcher."""

    assumption_set: AssumptionSet
    policies: list[PolicyStateBase]
    valuation_date: date | None = None
    run_id: str = ""
    assets: list[AssetRecord] = []


class SeriatimOutput(BaseModel):
    """Outputs of the seriatim dispatcher."""

    cash_flows: GrossCashFlows | None = None


def calculate(inputs: SeriatimInput) -> SeriatimOutput:
    """Run the seriatim projection for every policy in ``inputs.policies``.

    Args:
        inputs: Validated :class:`SeriatimInput`.

    Returns:
        Concatenated per-policy cash flows tagged for downstream
        aggregation.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

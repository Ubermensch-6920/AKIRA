"""
Seriatim dispatcher.

Routes a list of :class:`PolicyStateBase` records to the appropriate
product projection engine based on :attr:`PolicyStateBase.product_type`,
then concatenates the per-product cash flow outputs.
"""

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.policy import PolicyStateBase


class SeriatimInput(BaseModel):
    """Inputs to the seriatim dispatcher."""

    assumption_set: AssumptionSet
    policies: list[PolicyStateBase]
    # ASSUMPTION REQUIRED: cash flow grid + asset universe wiring


class SeriatimOutput(BaseModel):
    """Outputs of the seriatim dispatcher."""

    # ASSUMPTION REQUIRED: typed cash-flow container pending product spec
    cash_flows: dict = {}


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

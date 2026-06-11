"""
Seriatim dispatcher.

Routes a list of :class:`PolicyStateBase` records to the appropriate
product projection engine based on :attr:`PolicyStateBase.product_type`,
then concatenates the per-product cash flow outputs.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.enums import ProductType
from ..assumptions.sets import AssumptionSet
from ..models.asset import AssetRecord
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState, PolicyStateBase
from .projections import myga


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
        NotImplementedError: If any policy carries a product type whose
            projection engine is not yet implemented (Phase 2/3 products).
    """
    valuation_date = inputs.valuation_date or date.today()

    unsupported = sorted(
        {p.product_type.value for p in inputs.policies if p.product_type is not ProductType.MYGA}
    )
    if unsupported:
        raise NotImplementedError(
            f"No projection engine for product type(s): {', '.join(unsupported)}. "
            "Phase 1 supports MYGA only."
        )

    myga_policies = [p for p in inputs.policies if isinstance(p, MygaPolicyState)]
    myga_output = myga.calculate(
        myga.MygaProjectionInput(
            assumption_set=inputs.assumption_set,
            policies=myga_policies,
            valuation_date=valuation_date,
        )
    )

    cash_flows = myga_output.cash_flows or GrossCashFlows(
        valuation_date=valuation_date, policies=[]
    )
    return SeriatimOutput(cash_flows=cash_flows)

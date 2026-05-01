"""
Apply reinsurance treaties to gross cash flows.

Routes each policy → treaty pairing to the appropriate treaty-type
engine (quota share in Phase 1; coinsurance / modco / FWH / YRT / XL in
Phase 2) and produces ceded and net cash flow streams suitable for
downstream framework reserving.
"""

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.reinsurance import ReinsuranceTreaty


class ReinsuranceApplicationInput(BaseModel):
    """Inputs to the reinsurance application step."""

    assumption_set: AssumptionSet
    treaties: list[ReinsuranceTreaty]
    # ASSUMPTION REQUIRED: typed gross-cash-flow container pending product spec


class ReinsuranceApplicationOutput(BaseModel):
    """Output: ceded + net cash flow streams keyed by policy / treaty."""

    # ASSUMPTION REQUIRED: typed cash-flow containers pending product spec
    ceded_cash_flows: dict = {}
    net_cash_flows: dict = {}


def calculate(inputs: ReinsuranceApplicationInput) -> ReinsuranceApplicationOutput:
    """Apply each treaty to its associated policies' gross cash flows.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

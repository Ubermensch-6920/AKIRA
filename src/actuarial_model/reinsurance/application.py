"""
Apply reinsurance treaties to gross cash flows.

Routes each policy → treaty pairing to the appropriate treaty-type
engine (quota share in Phase 1; coinsurance / modco / FWH / YRT / XL in
Phase 2) and produces ceded and net cash flow streams suitable for
downstream framework reserving.
"""

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.cash_flows import GrossCashFlows
from ..models.reinsurance import ReinsuranceTreaty


class ReinsuranceApplicationInput(BaseModel):
    """Inputs to the reinsurance application step."""

    assumption_set: AssumptionSet
    treaties: list[ReinsuranceTreaty]
    gross_cash_flows: GrossCashFlows | None = None


class ReinsuranceApplicationOutput(BaseModel):
    """Output: ceded + net cash flow streams keyed by policy / treaty."""

    ceded_cash_flows: GrossCashFlows | None = None
    net_cash_flows: GrossCashFlows | None = None


def calculate(inputs: ReinsuranceApplicationInput) -> ReinsuranceApplicationOutput:
    """Apply each treaty to its associated policies' gross cash flows.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

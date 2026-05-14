"""
Quota-share reinsurance engine (Phase 1).

Applies a flat ``quota_share_pct`` to gross cash flows to derive ceded
and retained streams, including ceding commission and expense allowance
adjustments.
"""

from pydantic import BaseModel

from ..models.cash_flows import GrossCashFlows
from ..models.reinsurance import ReinsuranceTreaty


class QuotaShareInput(BaseModel):
    """Inputs to the quota-share engine."""

    treaty: ReinsuranceTreaty
    gross_cash_flows: GrossCashFlows | None = None


class QuotaShareOutput(BaseModel):
    """Output: ceded and retained cash flow streams."""

    ceded_cash_flows: GrossCashFlows | None = None
    retained_cash_flows: GrossCashFlows | None = None


def calculate(inputs: QuotaShareInput) -> QuotaShareOutput:
    """Apply a quota-share treaty to gross cash flows.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

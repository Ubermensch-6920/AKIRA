"""
Excess-of-Loss (XL) reinsurance engine (Phase 2 stub).

Layered reinsurance: cedent retains losses up to attachment; reinsurer
covers losses between attachment and limit.
"""

from pydantic import BaseModel

from ..models.reinsurance import ReinsuranceTreaty


class ExcessOfLossInput(BaseModel):
    """Inputs to the XL engine."""

    treaty: ReinsuranceTreaty


class ExcessOfLossOutput(BaseModel):
    """Output: ceded and retained cash flow streams."""

    ceded_cash_flows: dict = {}
    retained_cash_flows: dict = {}


def calculate(inputs: ExcessOfLossInput) -> ExcessOfLossOutput:
    """Apply an excess-of-loss treaty.

    Raises:
        NotImplementedError: Phase 2 stub — pending product spec.
    """
    raise NotImplementedError("Phase 2 — pending product spec")

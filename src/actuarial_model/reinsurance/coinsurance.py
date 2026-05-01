"""
Coinsurance reinsurance engine (Phase 2 stub).

Cedes the same proportional share of premiums, benefits, and expenses,
with the assets transferred to the reinsurer.
"""

from pydantic import BaseModel

from ..models.reinsurance import ReinsuranceTreaty


class CoinsuranceInput(BaseModel):
    """Inputs to the coinsurance engine."""

    treaty: ReinsuranceTreaty


class CoinsuranceOutput(BaseModel):
    """Output: ceded and retained cash flow streams."""

    ceded_cash_flows: dict = {}
    retained_cash_flows: dict = {}


def calculate(inputs: CoinsuranceInput) -> CoinsuranceOutput:
    """Apply a coinsurance treaty.

    Raises:
        NotImplementedError: Phase 2 stub — pending product spec.
    """
    raise NotImplementedError("Phase 2 — pending product spec")

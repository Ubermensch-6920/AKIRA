"""
Funds-Withheld (FWH) reinsurance engine (Phase 2 stub).

Coinsurance variant where the cedent withholds the assets and pays a
contractual interest rate on the funds-withheld balance.
"""

from pydantic import BaseModel

from ..models.reinsurance import ReinsuranceTreaty


class FundsWithheldInput(BaseModel):
    """Inputs to the funds-withheld engine."""

    treaty: ReinsuranceTreaty


class FundsWithheldOutput(BaseModel):
    """Output: ceded and retained cash flow streams."""

    ceded_cash_flows: dict = {}
    retained_cash_flows: dict = {}


def calculate(inputs: FundsWithheldInput) -> FundsWithheldOutput:
    """Apply a funds-withheld treaty.

    Raises:
        NotImplementedError: Phase 2 stub — pending product spec.
    """
    raise NotImplementedError("Phase 2 — pending product spec")

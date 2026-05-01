"""
Modified Coinsurance (ModCo) reinsurance engine (Phase 2 stub).

Coinsurance variant where assets supporting the ceded reserves are
retained by the cedent; reinsurer receives a ModCo interest credit.
"""

from pydantic import BaseModel

from ..models.reinsurance import ReinsuranceTreaty


class ModcoInput(BaseModel):
    """Inputs to the ModCo engine."""

    treaty: ReinsuranceTreaty


class ModcoOutput(BaseModel):
    """Output: ceded and retained cash flow streams."""

    ceded_cash_flows: dict = {}
    retained_cash_flows: dict = {}


def calculate(inputs: ModcoInput) -> ModcoOutput:
    """Apply a ModCo treaty.

    Raises:
        NotImplementedError: Phase 2 stub — pending product spec.
    """
    raise NotImplementedError("Phase 2 — pending product spec")

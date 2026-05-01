"""
Yearly Renewable Term (YRT) reinsurance engine (Phase 2 stub).

Mortality-only reinsurance with annually renewable rates.
"""

from pydantic import BaseModel

from ..models.reinsurance import ReinsuranceTreaty


class YrtInput(BaseModel):
    """Inputs to the YRT engine."""

    treaty: ReinsuranceTreaty


class YrtOutput(BaseModel):
    """Output: ceded and retained cash flow streams."""

    ceded_cash_flows: dict = {}
    retained_cash_flows: dict = {}


def calculate(inputs: YrtInput) -> YrtOutput:
    """Apply a YRT treaty.

    Raises:
        NotImplementedError: Phase 2 stub — pending product spec.
    """
    raise NotImplementedError("Phase 2 — pending product spec")

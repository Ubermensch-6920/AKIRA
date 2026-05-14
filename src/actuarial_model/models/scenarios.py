"""
Stochastic scenario path definitions.

:class:`ScenarioPath` represents a single interest-rate scenario used by
the stochastic capital engine (VM-22 SR, stochastic.py) and risk-transfer
testing (ASC 944 / SSAP 61R ERD method).
"""

from pydantic import BaseModel


class ScenarioPath(BaseModel):
    """A single stochastic interest-rate scenario path."""

    scenario_id: str
    period_rates: list[float]  # per-period risk-free rates as decimals (e.g. 0.04)

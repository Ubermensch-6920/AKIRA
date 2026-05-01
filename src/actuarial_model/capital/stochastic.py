"""
Stochastic capital calculation (scenario-driven).

Aggregates per-scenario losses into a CTE-style capital figure.
Generally aligns with VM-22 SR scenario sets but supports company-
defined scenarios as well.
"""

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.results import CapitalResult


class StochasticCapitalInput(BaseModel):
    """Inputs to the stochastic capital calculation."""

    assumption_set: AssumptionSet
    # ASSUMPTION REQUIRED: full input contract pending product spec


class StochasticCapitalOutput(BaseModel):
    """Output of the stochastic capital calculation."""

    capital_result: CapitalResult


def calculate(inputs: StochasticCapitalInput) -> StochasticCapitalOutput:
    """Compute stochastic CTE-based capital.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

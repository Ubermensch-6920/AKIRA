"""
ASC 820 fair-value liability calculation (formerly FAS 157).

Computes a fair-value liability with explicit risk margin (cost-of-
capital, CALM, or explicit), non-performance / own-credit risk
adjustment, and a configured discount basis.
"""

from pydantic import BaseModel

from ..assumptions.sets import AssumptionSet
from ..models.results import ReserveResult


class Fas157Input(BaseModel):
    """Inputs to the ASC 820 fair-value calculation."""

    assumption_set: AssumptionSet
    # ASSUMPTION REQUIRED: full input contract pending product spec


class Fas157Output(BaseModel):
    """Output of the ASC 820 fair-value calculation."""

    reserve_result: ReserveResult


def calculate(inputs: Fas157Input) -> Fas157Output:
    """Compute ASC 820 fair-value liability.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

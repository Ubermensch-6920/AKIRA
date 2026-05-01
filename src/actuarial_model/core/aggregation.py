"""
Roll-up of seriatim results: cohort → segment → legal entity → balance sheet.
"""

from pydantic import BaseModel

from ..models.results import ReserveResult


class AggregationInput(BaseModel):
    """Inputs to the aggregation roll-up."""

    seriatim_results: list[ReserveResult]


class AggregationOutput(BaseModel):
    """Output of aggregation: per-segment and per-legal-entity totals."""

    by_cohort: list[ReserveResult]
    by_segment: list[ReserveResult]
    by_legal_entity: list[ReserveResult]


def calculate(inputs: AggregationInput) -> AggregationOutput:
    """Aggregate per-policy results to cohort, segment, and legal-entity grain.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

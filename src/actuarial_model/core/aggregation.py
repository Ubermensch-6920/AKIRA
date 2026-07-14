"""
Roll-up of seriatim results: cohort → segment → legal entity → balance sheet.

Results are grouped within each reserving framework (mixing STAT and BEL
numbers in one total would be meaningless), then summed at three grains:

  - by_cohort:       (framework, legal_entity, segment, cohort_id)
  - by_segment:      (framework, legal_entity, segment)      cohort_id = "ALL"
  - by_legal_entity: (framework, legal_entity)               segment = cohort_id = "ALL"

Gross / ceded / net reserves are additive across policies and cohorts, so
each rolled-up :class:`ReserveResult` is a plain sum of its members. The
metadata of the first member stamps each group (all members of a group
share framework by construction; run and assumption-set IDs are expected
to be uniform within a run).
"""

from collections import defaultdict

from pydantic import BaseModel

from ..models.results import ReserveResult

METHODOLOGY_VERSION = "aggregation_v0.1.0"


class AggregationInput(BaseModel):
    """Inputs to the aggregation roll-up."""

    seriatim_results: list[ReserveResult]


class AggregationOutput(BaseModel):
    """Output of aggregation: per-segment and per-legal-entity totals."""

    by_cohort: list[ReserveResult]
    by_segment: list[ReserveResult]
    by_legal_entity: list[ReserveResult]


def calculate(inputs: AggregationInput) -> AggregationOutput:
    """Aggregate per-policy results to cohort, segment, and legal-entity grain."""
    results = inputs.seriatim_results
    return AggregationOutput(
        by_cohort=_roll_up(results, level="cohort"),
        by_segment=_roll_up(results, level="segment"),
        by_legal_entity=_roll_up(results, level="legal_entity"),
    )


def _group_key(result: ReserveResult, level: str) -> tuple[str, ...]:
    framework = result.metadata.framework.value
    if level == "cohort":
        return (framework, result.legal_entity, result.segment, result.cohort_id)
    if level == "segment":
        return (framework, result.legal_entity, result.segment)
    return (framework, result.legal_entity)


def _roll_up(results: list[ReserveResult], level: str) -> list[ReserveResult]:
    """Sum reserves within each group at the requested grain."""
    groups: dict[tuple[str, ...], list[ReserveResult]] = defaultdict(list)
    for result in results:
        groups[_group_key(result, level)].append(result)

    rolled: list[ReserveResult] = []
    for members in groups.values():
        first = members[0]
        rolled.append(
            ReserveResult(
                metadata=first.metadata,
                legal_entity=first.legal_entity,
                segment=first.segment if level in ("cohort", "segment") else "ALL",
                cohort_id=first.cohort_id if level == "cohort" else "ALL",
                gross_reserve=sum(m.gross_reserve for m in members),
                ceded_reserve=sum(m.ceded_reserve for m in members),
                net_reserve=sum(m.net_reserve for m in members),
                components={
                    "aggregation_level": level,
                    "source_result_count": len(members),
                },
            )
        )
    return rolled

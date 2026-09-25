"""
Roll-up of per-policy results: cohort → segment → legal entity.

Every basis measure carries a per-policy detail frame; aggregation stacks
them and sums with one polars ``group_by`` per grain. Groups are always
keyed by (basis, framework) first — mixing STAT and EBS numbers, or CARVM
and VM-22 within STAT, would be meaningless:

  - by_cohort:       (basis, framework, legal_entity, segment, cohort_id)
  - by_segment:      (basis, framework, legal_entity, segment)   cohort_id = "ALL"
  - by_legal_entity: (basis, framework, legal_entity)            segment = cohort_id = "ALL"

Gross / ceded / net are additive at policy grain (non-additive measures
allocate their run total to policies before reaching here), so each rolled
:class:`ReserveResult` is a plain sum.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl
from pydantic import BaseModel

from ..bases.common import MeasureResult
from ..models.results import ReserveResult, ResultMetadata

METHODOLOGY_VERSION = "aggregation_v1.0.0"

_GRAINS = {
    "cohort": ("legal_entity", "segment", "cohort_id"),
    "segment": ("legal_entity", "segment"),
    "legal_entity": ("legal_entity",),
}


class AggregationOutput(BaseModel):
    """Rolled-up results at each grain."""

    by_cohort: list[ReserveResult]
    by_segment: list[ReserveResult]
    by_legal_entity: list[ReserveResult]


def calculate(measures: Sequence[MeasureResult]) -> AggregationOutput:
    """Aggregate primary (non-supplementary) measures at every grain."""
    primary = [m for m in measures if not m.supplementary]
    stacked = _stack(primary)
    metadata_by_key = {_measure_key(m): m.reserve_result.metadata for m in primary}
    return AggregationOutput(
        by_cohort=_roll_up(stacked, "cohort", metadata_by_key),
        by_segment=_roll_up(stacked, "segment", metadata_by_key),
        by_legal_entity=_roll_up(stacked, "legal_entity", metadata_by_key),
    )


def _measure_key(measure: MeasureResult) -> str:
    meta = measure.reserve_result.metadata
    return f"{meta.basis.value}|{meta.framework.value}|{meta.methodology_version}"


def _stack(measures: Sequence[MeasureResult]) -> pl.DataFrame:
    frames = [
        m.policy_detail.with_columns(pl.lit(_measure_key(m)).alias("measure_key"))
        for m in measures
        if m.policy_detail.height
    ]
    if not frames:
        return pl.DataFrame(
            schema={
                "measure_key": pl.String(),
                "legal_entity": pl.String(),
                "segment": pl.String(),
                "cohort_id": pl.String(),
                "gross": pl.Float64(),
                "ceded": pl.Float64(),
                "net": pl.Float64(),
            }
        )
    return pl.concat(frames, how="diagonal_relaxed")


def _roll_up(
    stacked: pl.DataFrame,
    level: str,
    metadata_by_key: dict[str, ResultMetadata],
) -> list[ReserveResult]:
    keys = ["measure_key", *_GRAINS[level]]
    grouped = (
        stacked.group_by(keys, maintain_order=True)
        .agg(
            pl.col("gross").sum(),
            pl.col("ceded").sum(),
            pl.col("net").sum(),
            pl.len().alias("source_policy_count"),
        )
        .sort(keys)
    )
    return [
        ReserveResult(
            metadata=metadata_by_key[row["measure_key"]],
            legal_entity=row["legal_entity"],
            segment=row.get("segment", "ALL"),
            cohort_id=row.get("cohort_id", "ALL"),
            gross_reserve=row["gross"],
            ceded_reserve=row["ceded"],
            net_reserve=row["net"],
            components={
                "aggregation_level": level,
                "source_policy_count": row["source_policy_count"],
            },
        )
        for row in grouped.to_dicts()
    ]

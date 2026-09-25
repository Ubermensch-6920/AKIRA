"""
Valuation helpers shared by every basis.

Each basis measure returns a :class:`MeasureResult`: the run-level
:class:`ReserveResult` (what the API and RBC consume) plus a per-policy
detail frame (what aggregation rolls up to cohort / segment / legal entity).
Present values are computed on the projection frame in one pass:

    PV_i = sum_t outflow_i(t) * DF(tenor_t)

with the discount-factor vector evaluated once on the shared grid.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import polars as pl
from gaspatchio.curves import Curve

from ..assumptions.enums import Basis, Framework
from ..engine.curves import discount_factors
from ..engine.grid import grid_vector
from ..engine.projection import LABEL_COLUMNS, OUTFLOW_COLUMNS, Projection, list_sum
from ..models.results import CapitalResult, ReserveResult, ResultMetadata

DETAIL_COLUMNS = (*LABEL_COLUMNS, "gross", "ceded", "net")


@dataclass(frozen=True)
class RunStamp:
    """Identity every result of one valuation run is stamped with."""

    valuation_date: date
    run_id: str
    assumption_set_id: str

    def metadata(self, framework: Framework, methodology_version: str) -> ResultMetadata:
        return ResultMetadata(
            valuation_date=self.valuation_date,
            framework=framework,
            methodology_version=methodology_version,
            run_id=self.run_id,
            assumption_set_id=self.assumption_set_id,
        )


@dataclass(frozen=True)
class MeasureResult:
    """One basis measure: run total + per-policy detail.

    ``supplementary`` results (LDTI DAC, EBS risk margin) are reported but
    kept out of reserve aggregation and capital — DAC is an asset and the
    risk margin already sits inside the EBS technical provisions.
    """

    reserve_result: ReserveResult
    policy_detail: pl.DataFrame
    supplementary: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def framework(self) -> Framework:
        return self.reserve_result.metadata.framework


@dataclass
class BasisResult:
    """Everything one basis produced in a run."""

    basis: Basis
    measures: list[MeasureResult] = field(default_factory=list)
    capital: list[CapitalResult] = field(default_factory=list)

    def reserve_results(self, *, primary_only: bool = False) -> list[ReserveResult]:
        return [
            m.reserve_result for m in self.measures if not (primary_only and m.supplementary)
        ]


def pv_by_policy(
    projection: Projection,
    curve: Curve,
    columns: Sequence[str] = OUTFLOW_COLUMNS,
) -> pl.DataFrame:
    """Per-policy PV of the summed ``columns`` (``policy_id``, ``pv``)."""
    if projection.is_empty:
        return pl.DataFrame(schema={"policy_id": pl.String(), "pv": pl.Float64()})
    dfs = discount_factors(curve, projection.grid.payment_tenors)
    return projection.frame.select(
        "policy_id",
        (list_sum(columns) * grid_vector(dfs, pl.Float64())).list.sum().alias("pv"),
    )


def pv_weighted_duration(
    projection: Projection,
    curve: Curve,
    columns: Sequence[str] = OUTFLOW_COLUMNS,
) -> float:
    """Portfolio Macaulay duration (years) of the summed ``columns``; 0 if none."""
    if projection.is_empty:
        return 0.0
    tenors = projection.grid.payment_tenors
    dfs = discount_factors(curve, tenors)
    pv_t = [0.0] * len(tenors)
    for column in columns:
        for t, amount in enumerate(projection.total(column)):
            pv_t[t] += amount * dfs[t]
    total = sum(pv_t)
    return sum(pv * tenor for pv, tenor in zip(pv_t, tenors, strict=True)) / total if total > 0 else 0.0


def total_outflows(projection: Projection, columns: Sequence[str] = OUTFLOW_COLUMNS) -> float:
    """Undiscounted sum of the outflow lines across the portfolio."""
    return float(sum(sum(projection.total(c)) for c in columns))


def policy_detail(
    labels: pl.DataFrame,
    gross: pl.DataFrame,
    ceded: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Join per-policy gross and ceded amounts onto the label grain.

    ``gross`` / ``ceded`` are (policy_id, value) frames; missing ceded → 0.
    """
    detail = labels.join(gross.rename({gross.columns[1]: "gross"}), on="policy_id", how="left")
    if ceded is not None and ceded.height:
        detail = detail.join(ceded.rename({ceded.columns[1]: "ceded"}), on="policy_id", how="left")
    else:
        detail = detail.with_columns(pl.lit(0.0).alias("ceded"))
    return detail.with_columns(
        pl.col("gross").fill_null(0.0),
        pl.col("ceded").fill_null(0.0),
    ).with_columns((pl.col("gross") - pl.col("ceded")).alias("net")).select(DETAIL_COLUMNS)


def allocate(detail: pl.DataFrame, gross_total: float, ceded_total: float) -> pl.DataFrame:
    """Rescale per-policy gross / ceded to non-additive run totals (pro rata).

    Used where the run total is not a sum of policy amounts (VM-22 CTE,
    cost-of-capital risk margins): each policy keeps its share of the
    additive driver it was computed from.
    """

    def scaled(column: str, total: float) -> pl.Expr:
        driver = float(detail[column].sum())
        factor = total / driver if driver else 0.0
        return (pl.col(column) * factor).alias(column)

    return detail.with_columns(
        scaled("gross", gross_total), scaled("ceded", ceded_total)
    ).with_columns((pl.col("gross") - pl.col("ceded")).alias("net"))


def collapse_labels(labels: pl.DataFrame) -> tuple[str, str, str]:
    """Single (legal_entity, segment, cohort_id) for a run total; mixed → "ALL"."""

    def one(column: str) -> str:
        values = labels[column].unique().to_list() if labels.height else []
        return values[0] if len(values) == 1 else "ALL"

    return one("legal_entity"), one("segment"), one("cohort_id")


def reserve_result(
    stamp: RunStamp,
    framework: Framework,
    methodology_version: str,
    detail: pl.DataFrame,
    components: dict[str, Any],
    *,
    gross: float | None = None,
    ceded: float | None = None,
) -> ReserveResult:
    """Run-level :class:`ReserveResult` from a detail frame (totals overridable)."""
    gross_total = float(detail["gross"].sum()) if gross is None else gross
    ceded_total = float(detail["ceded"].sum()) if ceded is None else ceded
    legal_entity, segment, cohort_id = collapse_labels(detail)
    return ReserveResult(
        metadata=stamp.metadata(framework, methodology_version),
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        gross_reserve=gross_total,
        ceded_reserve=ceded_total,
        net_reserve=gross_total - ceded_total,
        components={"policy_count": detail.height, **components},
    )


def require_curve(curve_points: Sequence[object], measure: str) -> None:
    if not curve_points:
        raise ValueError(f"{measure}: curve_points is required for discounting.")

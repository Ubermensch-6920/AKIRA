"""
End-to-end valuation pipeline.

    seriatim policies
        │   (per basis assumption block, cached when blocks are identical)
        ▼
    gaspatchio projection ──► reinsurance split (gross / ceded / net)
        │
        ├──► STAT      CARVM · VM-22 · NAIC RBC
        ├──► US GAAP   ASC 820 fair value
        ├──► LDTI      LFPB · DAC
        └──► EBS       BEL · technical provisions (+ risk margin)
        │
        ▼
    aggregation (per basis & framework; cohort → segment → legal entity)

The REST layer and any batch job call :func:`run_valuation`; it has no I/O.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date

import polars as pl

from .assumptions.enums import Basis, Framework
from .assumptions.sets import AssumptionSet
from .bases import run_bases
from .bases.common import BasisResult, MeasureResult
from .bases.context import ValuationContext
from .engine import aggregation
from .engine.curves import CurvePoint
from .models.asset import AssetRecord
from .models.policy import MygaPolicyState
from .models.reinsurance import ReinsuranceTreaty
from .models.results import CapitalResult, ReserveResult


@dataclass(frozen=True)
class ValuationOutput:
    """All results of one run, demarcated by basis."""

    bases: dict[Basis, BasisResult]
    aggregation: aggregation.AggregationOutput
    projection_runs: int

    @property
    def measures(self) -> list[MeasureResult]:
        return [m for result in self.bases.values() for m in result.measures]

    @property
    def reserve_results(self) -> list[ReserveResult]:
        return [m.reserve_result for m in self.measures]

    @property
    def capital_results(self) -> list[CapitalResult]:
        return [c for result in self.bases.values() for c in result.capital]

    def policy_results(self) -> pl.DataFrame:
        """Per-policy results of every measure, tagged with basis / framework / component."""
        frames = []
        for m in self.measures:
            meta = m.reserve_result.metadata
            frames.append(
                m.policy_detail.with_columns(
                    pl.lit(meta.basis.value).alias("basis"),
                    pl.lit(meta.framework.value).alias("framework"),
                    pl.lit(m.reserve_result.components.get("component", "RESERVE")).alias(
                        "component"
                    ),
                    pl.lit(m.supplementary).alias("supplementary"),
                )
            )
        return pl.concat(frames, how="vertical_relaxed") if frames else pl.DataFrame()


def run_valuation(
    *,
    assumption_set: AssumptionSet,
    valuation_date: date,
    policies: Sequence[MygaPolicyState],
    curve_points: Sequence[CurvePoint],
    frameworks: Collection[Framework],
    treaties: Sequence[ReinsuranceTreaty] = (),
    assets: Sequence[AssetRecord] = (),
    total_adjusted_capital: float | None = None,
    run_id: str = "",
    projection_horizon_years: int = 30,
) -> ValuationOutput:
    """Project, reinsure, value every requested basis, and aggregate."""
    ctx = ValuationContext(
        assumption_set=assumption_set,
        valuation_date=valuation_date,
        policies=list(policies),
        curve_points=list(curve_points),
        run_id=run_id,
        treaties=list(treaties),
        assets=list(assets),
        total_adjusted_capital=total_adjusted_capital,
        projection_horizon_years=projection_horizon_years,
    )
    bases = run_bases(ctx, frameworks)
    measures = [m for result in bases.values() for m in result.measures]
    return ValuationOutput(
        bases=bases,
        aggregation=aggregation.calculate(measures),
        projection_runs=ctx.projection_runs,
    )

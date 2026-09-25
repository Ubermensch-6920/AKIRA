"""Request / response schemas for the runs and results routers."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from ...assumptions.enums import Framework
from ...assumptions.sets import AssumptionSet
from ...engine.curves import CurvePoint
from ...models.asset import AssetRecord
from ...models.policy import MygaPolicyState
from ...models.reinsurance import ReinsuranceTreaty
from ...models.runs import ValuationRun


def _default_frameworks() -> list[Framework]:
    # Every framework implemented in Phase 1, across all four bases.
    return [
        Framework.STAT_CARVM,
        Framework.STAT_VM22,
        Framework.NAIC_RBC,
        Framework.FAS157,
        Framework.LDTI,
        Framework.BEL,
        Framework.EBS,
    ]


class RunRequest(BaseModel):
    """POST /runs body — everything one valuation run needs."""

    valuation_date: date
    policies: list[MygaPolicyState]
    curve_points: list[CurvePoint]
    treaties: list[ReinsuranceTreaty] = []
    assets: list[AssetRecord] = []
    frameworks: list[Framework] = Field(default_factory=_default_frameworks)
    assumption_set: AssumptionSet | None = None  # default-configured set when omitted
    total_adjusted_capital: float | None = None  # enables the RBC ratio
    projection_horizon_years: int = Field(default=30, gt=0, le=100)
    submitted_by: str = "api"
    notes: str = ""


class BasisSummary(BaseModel):
    """One basis's results in a run response."""

    reserve_results: list[dict[str, Any]]
    capital_results: list[dict[str, Any]]


class RunResponse(BaseModel):
    """POST /runs response — the run record plus its results.

    ``bases`` is the demarcated view (STAT / US_GAAP / LDTI / EBS);
    ``reserve_results`` / ``capital_results`` are the same records flattened.
    """

    run: ValuationRun
    bases: dict[str, BasisSummary]
    reserve_results: list[dict[str, Any]]
    capital_results: list[dict[str, Any]]
    aggregation: dict[str, Any]
    projection_runs: int

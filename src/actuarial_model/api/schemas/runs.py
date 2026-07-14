"""Request / response schemas for the runs and results routers."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from ...assumptions.enums import Framework
from ...assumptions.sets import AssumptionSet
from ...core.discount import CurvePoint
from ...models.asset import AssetRecord
from ...models.policy import MygaPolicyState
from ...models.reinsurance import ReinsuranceTreaty
from ...models.runs import ValuationRun


def _default_frameworks() -> list[Framework]:
    # Every framework implemented in Phase 1.
    return [
        Framework.BEL,
        Framework.STAT_CARVM,
        Framework.STAT_VM22,
        Framework.NAIC_RBC,
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
    submitted_by: str = "api"
    notes: str = ""


class RunResponse(BaseModel):
    """POST /runs response — the run record plus its results."""

    run: ValuationRun
    reserve_results: list[dict[str, Any]]
    capital_results: list[dict[str, Any]]
    aggregation: dict[str, Any]

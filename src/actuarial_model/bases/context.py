"""
The valuation context every basis runs against.

Holds the run's inputs and a projection cache. Each framework config block
is a :class:`ProjectionBasisConfig`; bases ask the context for the gross /
ceded / net projection *on their own block*. Blocks with identical
projection assumptions share one gaspatchio run, so the default set (every
block equal) projects once while a margin-loaded STAT block projects
separately.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date

from ..assumptions.enums import Framework
from ..assumptions.sets import AssumptionSet, ProjectionBasisConfig
from ..engine import seriatim
from ..engine.curves import CurvePoint
from ..engine.projection import Projection
from ..models.asset import AssetRecord
from ..models.policy import MygaPolicyState
from ..models.reinsurance import ReinsuranceTreaty
from ..reinsurance import application
from .common import RunStamp

_PROJECTION_FIELDS = ("mortality", "lapse_config", "withdrawal", "creditor")


@dataclass(frozen=True)
class BasisProjection:
    """Gross, ceded (None when nothing is reinsured) and net on one block."""

    gross: Projection
    ceded: Projection | None
    net: Projection


@dataclass
class ValuationContext:
    """Inputs of one valuation run plus the per-block projection cache."""

    assumption_set: AssumptionSet
    valuation_date: date
    policies: list[MygaPolicyState]
    curve_points: list[CurvePoint]
    run_id: str = ""
    treaties: list[ReinsuranceTreaty] = field(default_factory=list)
    assets: list[AssetRecord] = field(default_factory=list)
    total_adjusted_capital: float | None = None
    projection_horizon_years: int = 30
    _cache: dict[str, BasisProjection] = field(default_factory=dict, repr=False)

    @property
    def stamp(self) -> RunStamp:
        return RunStamp(
            valuation_date=self.valuation_date,
            run_id=self.run_id,
            assumption_set_id=self.assumption_set.assumption_set_id,
        )

    def projection_for(self, framework: Framework) -> BasisProjection:
        """Gross / ceded / net projection on ``framework``'s assumption block."""
        return self.projection_on(self.assumption_set.framework_config(framework))

    def projection_on(self, config: ProjectionBasisConfig) -> BasisProjection:
        key = hashlib.sha256(
            config.model_dump_json(include=set(_PROJECTION_FIELDS)).encode()
        ).hexdigest()
        if key not in self._cache:
            gross = seriatim.project(
                self.policies,
                config,
                self.valuation_date,
                projection_horizon_years=self.projection_horizon_years,
            )
            ceded = None
            net = gross
            if self.treaties and not gross.is_empty:
                split = application.apply(gross, self.treaties)
                ceded, net = split.ceded, split.net
            self._cache[key] = BasisProjection(gross=gross, ceded=ceded, net=net)
        return self._cache[key]

    @property
    def projection_runs(self) -> int:
        """Distinct gaspatchio projections executed so far."""
        return len(self._cache)

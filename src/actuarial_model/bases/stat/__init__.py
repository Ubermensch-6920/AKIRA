"""
STAT basis — US statutory (NAIC).

  CARVM   (Pre-VM-22)  — greatest PV of guaranteed benefits      ``stat.carvm``
  VM-22   (DR + SR)    — projected outflows, CTE over scenarios  ``stat.vm22``
  NAIC RBC             — C-1…C-4 capital off the STAT reserves   (after the above)
"""

from __future__ import annotations

from collections.abc import Collection

from ...assumptions.enums import Basis, Framework
from ..common import BasisResult
from ..context import ValuationContext
from . import carvm, rbc, vm22

BASIS = Basis.STAT
FRAMEWORKS = (Framework.STAT_CARVM, Framework.STAT_VM22, Framework.NAIC_RBC)


def run(ctx: ValuationContext, frameworks: Collection[Framework]) -> BasisResult:
    """Run the requested STAT measures (reserves first, then RBC on them)."""
    stamp = ctx.stamp
    config = ctx.assumption_set.stat
    result = BasisResult(basis=BASIS)

    if Framework.STAT_CARVM in frameworks:
        result.measures.append(carvm.calculate(ctx.policies, config.carvm, stamp))
    if Framework.STAT_VM22 in frameworks:
        proj = ctx.projection_for(Framework.STAT_VM22)
        result.measures.append(
            vm22.calculate(proj.gross, proj.ceded, config.vm22, ctx.curve_points, stamp)
        )
    if Framework.NAIC_RBC in frameworks:
        result.capital.append(
            rbc.calculate(
                rbc.RbcInput(
                    assumption_set=ctx.assumption_set,
                    reserve_results=result.reserve_results(primary_only=True),
                    assets=ctx.assets,
                    valuation_date=ctx.valuation_date,
                    total_adjusted_capital=ctx.total_adjusted_capital,
                    run_id=ctx.run_id,
                )
            ).capital_result
        )
    return result

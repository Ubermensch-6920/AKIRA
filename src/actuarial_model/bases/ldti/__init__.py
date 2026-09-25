"""
LDTI basis — US GAAP ASC 944 Long-Duration Targeted Improvements.

  LFPB — liability for future policy benefits (NPR mechanics)   ``ldti``
  DAC  — deferred acquisition cost, straight-line (asset;        ``ldti``
         supplementary, never aggregated with reserves)
"""

from __future__ import annotations

from collections.abc import Collection

from ...assumptions.enums import Basis, Framework
from ..common import BasisResult
from ..context import ValuationContext
from . import dac, lfpb

BASIS = Basis.LDTI
FRAMEWORKS = (Framework.LDTI,)


def run(ctx: ValuationContext, frameworks: Collection[Framework]) -> BasisResult:
    """Run LFPB and DAC."""
    result = BasisResult(basis=BASIS)
    if Framework.LDTI in frameworks:
        config = ctx.assumption_set.ldti
        proj = ctx.projection_for(Framework.LDTI)
        result.measures.append(
            lfpb.calculate(
                proj.gross, proj.ceded, ctx.policies, config, ctx.curve_points, ctx.stamp
            )
        )
        result.measures.append(dac.calculate(ctx.policies, config, ctx.stamp))
    return result

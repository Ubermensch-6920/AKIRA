"""
EBS basis — Bermuda Economic Balance Sheet (BMA).

  BEL                   — risk-free best-estimate liability     ``ebs.bel``
  Technical provisions  — BEL @ risk-free + illiquidity premium  ``ebs.technical_provisions``
                          + cost-of-capital risk margin
  Risk margin           — supplementary (already inside the TP)
  ECR / BSCR            — Phase 3 stub (:mod:`.ecr`)
"""

from __future__ import annotations

from collections.abc import Collection

from ...assumptions.enums import Basis, Framework
from ..common import BasisResult
from ..context import ValuationContext
from . import bel, technical_provisions

BASIS = Basis.EBS
FRAMEWORKS = (Framework.BEL, Framework.EBS)


def run(ctx: ValuationContext, frameworks: Collection[Framework]) -> BasisResult:
    """Run the requested EBS measures."""
    config = ctx.assumption_set.ebs
    result = BasisResult(basis=BASIS)
    if Framework.BEL in frameworks:
        proj = ctx.projection_for(Framework.BEL)
        result.measures.append(
            bel.calculate(proj.gross, proj.ceded, config.bel, ctx.curve_points, ctx.stamp)
        )
    if Framework.EBS in frameworks:
        proj = ctx.projection_for(Framework.EBS)
        tp, risk_margin = technical_provisions.calculate(
            proj.gross,
            proj.ceded,
            config.technical_provisions,
            ctx.assumption_set.reinsurance,
            ctx.curve_points,
            ctx.stamp,
        )
        result.measures.extend([tp, risk_margin])
    return result

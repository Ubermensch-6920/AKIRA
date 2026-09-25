"""
US GAAP basis — outside ASC 944 LDTI.

  ASC 820 fair value (FAS 157) — exit-price liability   ``us_gaap.fas157``

LDTI (ASC 944) is reported as its own basis (:mod:`actuarial_model.bases.ldti`).
"""

from __future__ import annotations

from collections.abc import Collection

from ...assumptions.enums import Basis, Framework
from ..common import BasisResult
from ..context import ValuationContext
from . import fair_value

BASIS = Basis.US_GAAP
FRAMEWORKS = (Framework.FAS157,)


def run(ctx: ValuationContext, frameworks: Collection[Framework]) -> BasisResult:
    """Run the requested US GAAP (non-LDTI) measures."""
    result = BasisResult(basis=BASIS)
    if Framework.FAS157 in frameworks:
        proj = ctx.projection_for(Framework.FAS157)
        result.measures.append(
            fair_value.calculate(
                proj.gross,
                proj.ceded,
                ctx.assumption_set.us_gaap.fas157,
                ctx.curve_points,
                ctx.stamp,
            )
        )
    return result

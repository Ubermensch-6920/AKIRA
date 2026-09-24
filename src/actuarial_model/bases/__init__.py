"""
Accounting / regulatory bases — the top-level demarcation of AKIRA results.

    Basis     Package             Frameworks                         Assumption block
    ───────   ─────────────────   ────────────────────────────────   ──────────────────────
    STAT      bases.stat          STAT_CARVM, STAT_VM22, NAIC_RBC    assumption_set.stat
    US_GAAP   bases.us_gaap       FAS157 (ASC 820 fair value)        assumption_set.us_gaap
    LDTI      bases.ldti          LDTI (LFPB + DAC)                  assumption_set.ldti
    EBS       bases.ebs           BEL, EBS (TP + risk margin)        assumption_set.ebs

Each basis projects on its own assumption block (through the shared
gaspatchio engine), discounts on its own curve, and reports results stamped
with its :class:`~actuarial_model.assumptions.enums.Basis`. Results from
different bases are never summed; capital is computed inside its basis
(RBC in STAT; ECR will live in EBS).
"""

from __future__ import annotations

from collections.abc import Callable, Collection

from ..assumptions.enums import Basis, Framework
from . import ebs, ldti, stat, us_gaap
from .common import BasisResult
from .context import ValuationContext

BasisRunner = Callable[[ValuationContext, Collection[Framework]], BasisResult]

REGISTRY: dict[Basis, BasisRunner] = {
    Basis.STAT: stat.run,
    Basis.US_GAAP: us_gaap.run,
    Basis.LDTI: ldti.run,
    Basis.EBS: ebs.run,
}


def run_bases(ctx: ValuationContext, frameworks: Collection[Framework]) -> dict[Basis, BasisResult]:
    """Run every basis that has at least one requested framework."""
    requested = set(frameworks)
    return {
        basis: runner(ctx, requested)
        for basis, runner in REGISTRY.items()
        if any(f.basis is basis for f in requested)
    }


__all__ = ["REGISTRY", "BasisResult", "ValuationContext", "run_bases"]

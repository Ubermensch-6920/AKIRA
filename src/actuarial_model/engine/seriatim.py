"""
Seriatim dispatcher.

Routes policy records to their product's gaspatchio model by
:attr:`PolicyStateBase.product_type` and returns one :class:`Projection`
on the shared valuation-date grid.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from ..assumptions.enums import ProductType
from ..assumptions.sets import ProjectionBasisConfig
from ..models.policy import MygaPolicyState, PolicyStateBase
from .projection import Projection
from .projections import myga


def project(
    policies: Sequence[PolicyStateBase],
    config: ProjectionBasisConfig,
    valuation_date: date,
    *,
    projection_horizon_years: int = 30,
    detail: bool = False,
) -> Projection:
    """Project every policy on ``config`` from ``valuation_date``.

    Raises:
        NotImplementedError: If any policy carries a product type whose
            projection model is not yet implemented (Phase 2/3 products).
    """
    unsupported = sorted(
        {p.product_type.value for p in policies if p.product_type is not ProductType.MYGA}
    )
    if unsupported:
        raise NotImplementedError(
            f"No projection engine for product type(s): {', '.join(unsupported)}. "
            "Phase 1 supports MYGA only."
        )
    myga_policies = [p for p in policies if isinstance(p, MygaPolicyState)]
    return myga.project(
        myga_policies,
        config,
        valuation_date,
        projection_horizon_years=projection_horizon_years,
        detail=detail,
    )

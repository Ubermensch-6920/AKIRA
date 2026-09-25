"""
LDTI — Deferred Acquisition Cost (ASC 944-30, post-LDTI).

Deferrable cost = ``acquisition_cost_pct`` * single premium per policy,
amortized straight-line over the guarantee period on a constant-basis (no
interest) schedule. Reported as a supplementary result: DAC is an asset,
not a reserve, so it never enters reserve aggregation or capital.

The EGP (legacy) basis raises NotImplementedError.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from ...assumptions.enums import DacBasis, Framework
from ...assumptions.sets import LdtiConfig
from ...engine.grid import months_between
from ...engine.projection import LABEL_COLUMNS
from ...models.policy import MygaPolicyState
from ..common import DETAIL_COLUMNS, MeasureResult, RunStamp, reserve_result

METHODOLOGY_VERSION = "ldti_dac_v1.0.0"


def unamortized_dac(policy: MygaPolicyState, acquisition_cost_pct: float, valuation_date) -> float:
    """Unamortized DAC for one policy (straight-line over the guarantee term)."""
    deferrable = acquisition_cost_pct * policy.single_premium
    total_months = policy.guarantee_period_years * 12
    if deferrable <= 0.0 or total_months <= 0:
        return 0.0
    elapsed = months_between(policy.issue_date, valuation_date)
    remaining_fraction = 1.0 - min(max(elapsed, 0), total_months) / total_months
    return deferrable * remaining_fraction


def calculate(
    policies: Sequence[MygaPolicyState],
    config: LdtiConfig,
    stamp: RunStamp,
) -> MeasureResult:
    """Unamortized DAC balance per policy and in total.

    Raises:
        NotImplementedError: For the EGP (legacy) DAC basis.
    """
    if config.dac_basis is not DacBasis.STRAIGHT_LINE:
        raise NotImplementedError(
            f"DAC basis {config.dac_basis.value} is not implemented in "
            "Phase 1 — use STRAIGHT_LINE."
        )
    balances = [
        unamortized_dac(p, config.acquisition_cost_pct, stamp.valuation_date) for p in policies
    ]
    detail = pl.DataFrame(
        {
            "policy_id": [p.policy_id for p in policies],
            "legal_entity": [p.legal_entity for p in policies],
            "segment": [p.segment for p in policies],
            "cohort_id": [p.cohort_id for p in policies],
            "gross": balances,
            "ceded": [0.0] * len(policies),
            "net": balances,
        },
        schema={
            **{name: pl.String() for name in LABEL_COLUMNS},
            "gross": pl.Float64(),
            "ceded": pl.Float64(),
            "net": pl.Float64(),
        },
    ).select(DETAIL_COLUMNS)
    result = reserve_result(
        stamp,
        Framework.LDTI,
        METHODOLOGY_VERSION,
        detail,
        {
            "component": "DAC",
            "sign_convention": "ASSET",
            "dac_basis": config.dac_basis.value,
            "acquisition_cost_pct": config.acquisition_cost_pct,
        },
    )
    return MeasureResult(reserve_result=result, policy_detail=detail, supplementary=True)

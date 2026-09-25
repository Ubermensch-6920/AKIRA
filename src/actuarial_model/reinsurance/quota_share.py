"""
Quota-share reinsurance engine (Phase 1).

A quota share cedes a flat ``quota_share_pct`` of every monetary cash-flow
line. On the projection frame that is one multiplication per list column:
ceded = gross x pct, retained = gross x (1 - pct). ``lives_in_force`` is a
policy count, not money, so it is carried unchanged on both streams (the
risk is shared, the policies are not).

Phase 1 simplifications (documented for review):
  - Ceding commission / expense allowance are not modeled as cash flows:
    the MYGA projection carries no premium or expense lines for them to
    attach to. The treaty's ``ceding_commission_pct`` is echoed for
    downstream use.
  - The treaty is assumed in force for the full projection: effective /
    termination dates are not applied period-by-period.
"""

from __future__ import annotations

import polars as pl

from ..assumptions.enums import ReinsuranceTreatyType
from ..engine.projection import CASH_FLOW_COLUMNS
from ..models.reinsurance import ReinsuranceTreaty

METHODOLOGY_VERSION = "quota_share_v1.0.0"


def validate_treaty(treaty: ReinsuranceTreaty) -> float:
    """Check a treaty is a well-formed quota share; return its ceded share.

    Raises:
        ValueError: If the treaty is not quota-share, or ``quota_share_pct``
            is missing or outside [0, 1].
    """
    if treaty.treaty_type is not ReinsuranceTreatyType.QUOTA_SHARE:
        raise ValueError(
            f"Treaty {treaty.treaty_id} is {treaty.treaty_type.value}; "
            "the quota-share engine handles QUOTA_SHARE treaties only."
        )
    if treaty.quota_share_pct is None:
        raise ValueError(f"Treaty {treaty.treaty_id} has no quota_share_pct.")
    pct = treaty.quota_share_pct
    if not 0.0 <= pct <= 1.0:
        raise ValueError(f"Treaty {treaty.treaty_id} quota_share_pct={pct} must be in [0, 1].")
    return pct


def split(frame: pl.DataFrame, pct: pl.Expr | float) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Split every monetary list column into (ceded, retained) frames.

    ``pct`` may be a scalar or a per-row expression (the ceded share of each
    policy), which is how :mod:`.application` applies many treaties at once.
    """
    share = pct if isinstance(pct, pl.Expr) else pl.lit(pct)
    ceded = frame.with_columns([(pl.col(c) * share).alias(c) for c in CASH_FLOW_COLUMNS])
    retained = frame.with_columns(
        [(pl.col(c) * (1.0 - share)).alias(c) for c in CASH_FLOW_COLUMNS]
    )
    return ceded, retained

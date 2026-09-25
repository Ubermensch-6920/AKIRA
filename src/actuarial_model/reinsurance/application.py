"""
Apply reinsurance treaties to a gross projection.

Each policy names at most one treaty via ``reinsurance_treaty_id`` (carried
on the projection frame from the seriatim record, or supplied explicitly).
The treaty's ceded share becomes a per-policy column, and the whole
portfolio is split in one vectorised pass — gross, ceded, and net stay on
the same grid, so every basis discounts all three identically.

Output streams:
  - ceded: reinsured policies only
  - net:   every policy (retained share where reinsured, gross otherwise)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import polars as pl

from ..assumptions.enums import ReinsuranceTreatyType
from ..engine.projection import Projection
from ..models.reinsurance import ReinsuranceTreaty
from . import quota_share

METHODOLOGY_VERSION = "reinsurance_application_v1.0.0"

_TREATY_COLUMN = "reinsurance_treaty_id"
_SHARE_COLUMN = "_ceded_share"


@dataclass(frozen=True)
class ReinsuranceSplit:
    """Ceded and net projections derived from one gross projection."""

    ceded: Projection
    net: Projection


def apply(
    gross: Projection,
    treaties: Sequence[ReinsuranceTreaty],
    treaty_id_by_policy: Mapping[str, str | None] | None = None,
) -> ReinsuranceSplit:
    """Split ``gross`` into ceded and net streams per each policy's treaty.

    Args:
        gross: Gross projection.
        treaties: Treaty registry.
        treaty_id_by_policy: Overrides / supplies the policy → treaty pairing
            when the projection frame carries no ``reinsurance_treaty_id``.

    Raises:
        ValueError: If a policy names a treaty not in ``treaties`` or a
            treaty is malformed.
        NotImplementedError: If a paired treaty is a Phase 2 type
            (coinsurance / ModCo / FWH / YRT / XL).
    """
    frame = gross.frame
    if treaty_id_by_policy is not None:
        mapping = pl.DataFrame(
            {
                "policy_id": list(treaty_id_by_policy),
                _TREATY_COLUMN: list(treaty_id_by_policy.values()),
            },
            schema={"policy_id": pl.String(), _TREATY_COLUMN: pl.String()},
        )
        frame = frame.drop(_TREATY_COLUMN, strict=False).join(mapping, on="policy_id", how="left")
    elif _TREATY_COLUMN not in frame.columns:
        frame = frame.with_columns(pl.lit(None, dtype=pl.String()).alias(_TREATY_COLUMN))

    treaty_by_id = {t.treaty_id: t for t in treaties}
    shares: dict[str, float] = {}
    for treaty_id in frame[_TREATY_COLUMN].drop_nulls().unique().to_list():
        treaty = treaty_by_id.get(treaty_id)
        if treaty is None:
            offenders = frame.filter(pl.col(_TREATY_COLUMN) == treaty_id)["policy_id"].to_list()
            raise ValueError(
                f"Policy {offenders[0]} references treaty {treaty_id!r}, "
                "which is not in the supplied treaty list."
            )
        if treaty.treaty_type is not ReinsuranceTreatyType.QUOTA_SHARE:
            raise NotImplementedError(
                f"Treaty {treaty.treaty_id} is {treaty.treaty_type.value}; "
                "Phase 1 supports QUOTA_SHARE only."
            )
        shares[treaty_id] = quota_share.validate_treaty(treaty)

    share_expr = (
        pl.col(_TREATY_COLUMN).replace_strict(shares, default=0.0, return_dtype=pl.Float64())
        if shares
        else pl.lit(0.0)
    )
    frame = frame.with_columns(share_expr.alias(_SHARE_COLUMN))
    ceded, net = quota_share.split(frame, pl.col(_SHARE_COLUMN))
    ceded = ceded.filter(pl.col(_TREATY_COLUMN).is_not_null()).drop(_SHARE_COLUMN)
    net = net.drop(_SHARE_COLUMN)
    return ReinsuranceSplit(ceded=gross.with_frame(ceded), net=gross.with_frame(net))

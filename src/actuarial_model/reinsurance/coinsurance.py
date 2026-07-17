"""
Coinsurance reinsurance engine (Phase 2).

Cedes the same proportional share (``coinsurance_pct``) of all benefit
cash flows, with the assets supporting the ceded reserves transferred to
the reinsurer. At benefit-stream granularity the split is identical to
quota share; the distinguishing economics — premium/asset transfer and
the reinsurer's investment risk on the transferred portfolio — sit on
the asset side, which is not yet modeled per treaty (the transfer is
recorded in the output for downstream asset accounting).

Phase 2 simplifications (documented for review):
  - Ceding commission / expense allowances are not modeled as cash flows
    (no premium or expense fields on the MYGA record yet).
  - Treaty effective / termination windows are not applied period-by-period.
"""

from pydantic import BaseModel

from ..assumptions.enums import ReinsuranceTreatyType
from ..models.cash_flows import GrossCashFlows
from ..models.reinsurance import ReinsuranceTreaty
from .proportional import split_proportional, validate_share

METHODOLOGY_VERSION = "coinsurance_v0.1.0"


class CoinsuranceInput(BaseModel):
    """Inputs to the coinsurance engine."""

    treaty: ReinsuranceTreaty
    gross_cash_flows: GrossCashFlows | None = None


class CoinsuranceOutput(BaseModel):
    """Output: ceded and retained cash flow streams."""

    ceded_cash_flows: GrossCashFlows | None = None
    retained_cash_flows: GrossCashFlows | None = None
    # Initial asset transfer to the reinsurer: ceded share of AV at the
    # first projection period (statutory initial reserve proxy).
    initial_asset_transfer: float = 0.0


def calculate(inputs: CoinsuranceInput) -> CoinsuranceOutput:
    """Apply a coinsurance treaty to gross cash flows.

    Raises:
        ValueError: If the treaty is not coinsurance, ``coinsurance_pct``
            is missing/out of range, or ``gross_cash_flows`` is absent.
    """
    treaty = inputs.treaty
    if treaty.treaty_type is not ReinsuranceTreatyType.COINSURANCE:
        raise ValueError(
            f"Treaty {treaty.treaty_id} is {treaty.treaty_type.value}; "
            "the coinsurance engine handles COINSURANCE treaties only."
        )
    pct = validate_share(treaty.treaty_id, "coinsurance_pct", treaty.coinsurance_pct)
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "CoinsuranceInput.gross_cash_flows is required — run the "
            "projection engine (core.seriatim) first."
        )

    ceded, retained = split_proportional(inputs.gross_cash_flows, pct)
    initial_transfer = sum(
        policy_cf.records[0].account_value_bop
        for policy_cf in ceded.policies
        if policy_cf.records
    )
    return CoinsuranceOutput(
        ceded_cash_flows=ceded,
        retained_cash_flows=retained,
        initial_asset_transfer=initial_transfer,
    )

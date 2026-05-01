"""
Reinsurance treaty records.

Phase 1 implements quota-share fields only; other treaty-type fields are
present but optional and remain inert until Phase 2.
"""

from datetime import date

from pydantic import BaseModel

from ..assumptions.enums import (
    CollateralType,
    ReinsuranceTreatyType,
    ReinsurerAuthStatus,
    RiskTransferMethod,
)


class ReinsuranceTreaty(BaseModel):
    """
    Single treaty record.

    Phase 1 implements ``quota_share_pct``; other treaty-type fields are
    optional and populated in later phases.
    """

    treaty_id: str
    treaty_name: str
    counterparty: str
    counterparty_rating: str
    auth_status: ReinsurerAuthStatus
    treaty_type: ReinsuranceTreatyType
    effective_date: date
    termination_date: date | None = None

    # Quota share (Phase 1)
    quota_share_pct: float | None = None

    # Phase 2 — stubbed
    coinsurance_pct: float | None = None
    modco_interest_rate: float | None = None
    funds_withheld_rate: float | None = None
    xl_attachment: float | None = None
    xl_limit: float | None = None
    yrt_premium_scale: str | None = None

    # Common provisions
    ceding_commission_pct: float | None = None
    expense_allowance_pct: float | None = None
    experience_refund_pct: float | None = None

    # Collateral
    collateral_type: CollateralType = CollateralType.NONE
    collateral_amount: float | None = None

    # Framework treatment
    risk_transfer_method: RiskTransferMethod
    qualifies_for_credit_stat: bool = True
    qualifies_for_credit_gaap: bool = True
    bma_haircut_pct: float | None = None

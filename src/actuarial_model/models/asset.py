"""
Asset master records.

A single :class:`AssetRecord` is the source of truth for an asset.
Framework-specific views (book vs. fair vs. EBS market) are computed in
:mod:`actuarial_model.assets.valuation` on top of this record.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class AssetRecord(BaseModel):
    """Single source of truth for an asset position."""

    asset_id: str
    cusip: str | None = None
    issuer: str
    sector: str
    asset_type: str  # BOND | MORTGAGE | STRUCTURED | EQUITY | CASH
    coupon_rate: float | None = None
    maturity_date: date | None = None
    par_amount: float

    # Book / amortized basis
    book_value: float
    amortized_cost: float

    # Market basis
    market_value: float
    fair_value_level: Literal["LEVEL_1", "LEVEL_2", "LEVEL_3"]
    unrealized_gl: float
    oas_spread: float | None = None

    # Risk metrics
    credit_rating: str  # S&P style
    naic_designation: int  # 1–6
    modified_duration: float | None = None
    convexity: float | None = None
    spread_duration: float | None = None

    # Classifications
    gaap_classification: Literal["HTM", "AFS", "TRADING"]
    admitted_flag: bool
    bma_asset_class: str | None = None
    market_value_ebs: float | None = None  # post-haircut

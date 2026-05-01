"""
Per-policy state records.

The :class:`PolicyStateBase` defines the fields common to every product.
Each product subclass narrows ``product_type`` to a Literal so that the
core seriatim dispatcher can route on the discriminator. Field lists for
the product-specific subclasses are placeholders until the product spec
arrives.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from ..assumptions.enums import ProductType


class PolicyStateBase(BaseModel):
    """Base policy state — common fields across all products."""

    policy_id: str
    product_type: ProductType
    issue_date: date
    issue_age: int
    sex: Literal["M", "F", "U"]
    issue_state: str
    legal_entity: str
    segment: str
    cohort_id: str
    valuation_date: date


class MygaPolicyState(PolicyStateBase):
    """
    MYGA-specific policy state.

    Field list to be finalized once product spec is provided. Placeholder
    fields below — refine after product_spec arrives.
    """

    product_type: Literal[ProductType.MYGA] = ProductType.MYGA
    # ASSUMPTION REQUIRED: confirm full field list from product spec
    single_premium: float
    account_value: float
    guaranteed_rate: float
    guarantee_period_years: int
    guarantee_end_date: date
    surrender_charge_schedule_id: str
    has_mva: bool = False
    death_benefit_basis: str = "ROAV"  # ROAV | ROP | OTHER
    free_withdrawal_pct: float = 0.10
    reinsurance_treaty_id: str | None = None


# ── Phase 2 / 3 stubs — to be fleshed out per product ────────────────────
class FiaPolicyState(PolicyStateBase):
    """Fixed Indexed Annuity. Phase 2 stub."""

    product_type: Literal[ProductType.FIA] = ProductType.FIA


class SpiaPolicyState(PolicyStateBase):
    """Single Premium Immediate Annuity. Phase 2 stub."""

    product_type: Literal[ProductType.SPIA] = ProductType.SPIA


class PrtPolicyState(PolicyStateBase):
    """Pension Risk Transfer. Phase 2 stub."""

    product_type: Literal[ProductType.PRT] = ProductType.PRT


class VaPolicyState(PolicyStateBase):
    """Variable Annuity. Phase 3 stub."""

    product_type: Literal[ProductType.VA] = ProductType.VA


class UlsgPolicyState(PolicyStateBase):
    """Universal Life with Secondary Guarantee. Phase 3 stub."""

    product_type: Literal[ProductType.ULSG] = ProductType.ULSG

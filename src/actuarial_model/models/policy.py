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

    Field list aligned to the Athene product documents backing the
    embedded surrender schedules (MYG — doc 76009; MaxRate — doc 76047):

      - Free withdrawals: MYG allows 10% of accumulated value each
        contract year (``free_withdrawal_basis="PCT_AV"``); MaxRate's
        free amount is the interest earned — fixed strategy rate times
        the anniversary AV (``free_withdrawal_basis="INTEREST_EARNED"``,
        under which ``free_withdrawal_pct`` is ignored).
      - Death benefit: both products pay the full accumulated value with
        no withdrawal charge or MVA (``death_benefit_basis="ROAV"``).
      - Nonforfeiture: cash surrender values are floored at the Minimum
        Guaranteed Surrender Value — ``mgsv_premium_pct`` of the single
        premium accumulated at ``nonforfeiture_rate`` (ASSUMPTION
        REQUIRED: set the contract's actual nonforfeiture rate; the SNFL
        corridor is 1% to 3%).
    """

    product_type: Literal[ProductType.MYGA] = ProductType.MYGA
    single_premium: float
    account_value: float
    guaranteed_rate: float
    guarantee_period_years: int
    guarantee_end_date: date
    surrender_charge_schedule_id: str
    has_mva: bool = False
    death_benefit_basis: str = "ROAV"  # ROAV | ROP | OTHER
    free_withdrawal_basis: Literal["PCT_AV", "INTEREST_EARNED"] = "PCT_AV"
    free_withdrawal_pct: float = 0.10
    mgsv_premium_pct: float = 0.875
    nonforfeiture_rate: float = 0.01
    reinsurance_treaty_id: str | None = None

    def free_withdrawal_fraction(self) -> float:
        """Annual free-withdrawal corridor as a fraction of account value."""
        if self.free_withdrawal_basis == "INTEREST_EARNED":
            return self.guaranteed_rate
        return self.free_withdrawal_pct

    def mgsv_at(self, months_since_issue: int) -> float:
        """Minimum Guaranteed Surrender Value after ``months_since_issue``."""
        years = max(months_since_issue, 0) / 12.0
        return (
            self.mgsv_premium_pct
            * self.single_premium
            * (1.0 + self.nonforfeiture_rate) ** years
        )


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

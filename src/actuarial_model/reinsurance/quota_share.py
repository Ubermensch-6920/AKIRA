"""
Quota-share reinsurance engine (Phase 1).

Applies a flat ``quota_share_pct`` to gross cash flows to derive ceded
and retained streams. Every monetary field on each cash-flow record is
split proportionally; ``lives_in_force`` is a policy count, not a
monetary amount, so it is carried unchanged on both streams (the risk is
shared, the policies are not).

Phase 1 simplifications (documented for review):
  - Ceding commission / expense allowance are not modeled as cash flows:
    the MYGA cash-flow record carries no premium or expense fields, so
    there is no stream for the commission to attach to. The treaty's
    ``ceding_commission_pct`` is echoed in the output for downstream use.
  - The treaty is assumed in force for the full projection: effective /
    termination dates are not applied period-by-period.
"""

from pydantic import BaseModel

from ..assumptions.enums import ReinsuranceTreatyType
from ..models.cash_flows import GrossCashFlows, MygaCashFlowRecord, PolicyCashFlows
from ..models.reinsurance import ReinsuranceTreaty

METHODOLOGY_VERSION = "quota_share_v0.1.0"

# Monetary fields on MygaCashFlowRecord that split proportionally under QS.
_MONETARY_FIELDS = (
    "account_value_bop",
    "interest_credited",
    "partial_withdrawals",
    "surrender_charge",
    "mva_adjustment",
    "surrender_benefits",
    "death_benefits",
    "maturity_benefits",
    "account_value_eop",
)


class QuotaShareInput(BaseModel):
    """Inputs to the quota-share engine."""

    treaty: ReinsuranceTreaty
    gross_cash_flows: GrossCashFlows | None = None


class QuotaShareOutput(BaseModel):
    """Output: ceded and retained cash flow streams."""

    ceded_cash_flows: GrossCashFlows | None = None
    retained_cash_flows: GrossCashFlows | None = None


def calculate(inputs: QuotaShareInput) -> QuotaShareOutput:
    """Apply a quota-share treaty to gross cash flows.

    Raises:
        ValueError: If the treaty is not quota-share, ``quota_share_pct``
            is missing or outside [0, 1], or ``gross_cash_flows`` is absent.
    """
    treaty = inputs.treaty
    if treaty.treaty_type is not ReinsuranceTreatyType.QUOTA_SHARE:
        raise ValueError(
            f"Treaty {treaty.treaty_id} is {treaty.treaty_type.value}; "
            "the quota-share engine handles QUOTA_SHARE treaties only."
        )
    if treaty.quota_share_pct is None:
        raise ValueError(f"Treaty {treaty.treaty_id} has no quota_share_pct.")
    pct = treaty.quota_share_pct
    if not 0.0 <= pct <= 1.0:
        raise ValueError(
            f"Treaty {treaty.treaty_id} quota_share_pct={pct} must be in [0, 1]."
        )
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "QuotaShareInput.gross_cash_flows is required — run the "
            "projection engine (core.seriatim) first."
        )

    gross = inputs.gross_cash_flows
    ceded_policies: list[PolicyCashFlows] = []
    retained_policies: list[PolicyCashFlows] = []
    for policy_cf in gross.policies:
        ceded_policies.append(
            PolicyCashFlows(
                policy_id=policy_cf.policy_id,
                records=[_scale_record(r, pct) for r in policy_cf.records],
            )
        )
        retained_policies.append(
            PolicyCashFlows(
                policy_id=policy_cf.policy_id,
                records=[_scale_record(r, 1.0 - pct) for r in policy_cf.records],
            )
        )

    return QuotaShareOutput(
        ceded_cash_flows=GrossCashFlows(
            valuation_date=gross.valuation_date, policies=ceded_policies
        ),
        retained_cash_flows=GrossCashFlows(
            valuation_date=gross.valuation_date, policies=retained_policies
        ),
    )


def _scale_record(record: MygaCashFlowRecord, share: float) -> MygaCashFlowRecord:
    """Copy of ``record`` with every monetary field scaled by ``share``."""
    scaled = {field: getattr(record, field) * share for field in _MONETARY_FIELDS}
    return record.model_copy(update=scaled)

"""
Shared proportional cash-flow splitting for pro-rata treaty structures.

Quota share, coinsurance, ModCo, and funds withheld all cede the same
proportional share of every monetary benefit field; the structures then
differ in asset and settlement mechanics layered on top. This module
holds the common split so each engine only implements its differences.

``lives_in_force`` is a policy count, not a monetary amount, so it is
carried unchanged on both streams (the risk is shared, the policies are
not).
"""

from ..models.cash_flows import GrossCashFlows, MygaCashFlowRecord, PolicyCashFlows

# Monetary fields on MygaCashFlowRecord that split proportionally.
MONETARY_FIELDS = (
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


def scale_record(record: MygaCashFlowRecord, share: float) -> MygaCashFlowRecord:
    """Copy of ``record`` with every monetary field scaled by ``share``."""
    scaled = {field: getattr(record, field) * share for field in MONETARY_FIELDS}
    return record.model_copy(update=scaled)


def split_proportional(
    gross: GrossCashFlows, ceded_share: float
) -> tuple[GrossCashFlows, GrossCashFlows]:
    """Split ``gross`` into (ceded, retained) streams at ``ceded_share``."""
    ceded_policies: list[PolicyCashFlows] = []
    retained_policies: list[PolicyCashFlows] = []
    for policy_cf in gross.policies:
        ceded_policies.append(
            PolicyCashFlows(
                policy_id=policy_cf.policy_id,
                records=[scale_record(r, ceded_share) for r in policy_cf.records],
            )
        )
        retained_policies.append(
            PolicyCashFlows(
                policy_id=policy_cf.policy_id,
                records=[scale_record(r, 1.0 - ceded_share) for r in policy_cf.records],
            )
        )
    return (
        GrossCashFlows(valuation_date=gross.valuation_date, policies=ceded_policies),
        GrossCashFlows(valuation_date=gross.valuation_date, policies=retained_policies),
    )


def validate_share(treaty_id: str, name: str, share: float | None) -> float:
    """Common share validation: present and within [0, 1]."""
    if share is None:
        raise ValueError(f"Treaty {treaty_id} has no {name}.")
    if not 0.0 <= share <= 1.0:
        raise ValueError(f"Treaty {treaty_id} {name}={share} must be in [0, 1].")
    return share

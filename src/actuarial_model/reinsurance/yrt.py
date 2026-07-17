"""
Yearly Renewable Term (YRT) reinsurance engine (Phase 2).

Mortality-only reinsurance: the reinsurer covers a share
(``quota_share_pct``, default 100%) of death claims and nothing else —
surrenders, withdrawals, maturities, and account-value mechanics stay
entirely with the cedent.

For a MYGA the net amount at risk is the death benefit in excess of the
account value. Under a return-of-account-value basis (``ROAV``) the NAR
is zero, so there is nothing to cede; only return-of-premium (``ROP``)
policies generate YRT claims. Phase 2 cedes the full death benefit on
ROP policies as an upper-bound proxy (ASSUMPTION REQUIRED: refine to the
strict NAR = max(premium - AV, 0) basis once the per-policy AV path is
exposed on the cash-flow record).

Phase 2 simplifications (documented for review):
  - YRT premiums (``yrt_premium_scale``) are not modeled — no premium
    stream exists on the MYGA record; net cost is therefore overstated
    in the ceded stream's favor.
  - Rate renewal / recapture-on-rate-increase dynamics are not modeled.
"""

from pydantic import BaseModel

from ..assumptions.enums import ReinsuranceTreatyType
from ..models.cash_flows import GrossCashFlows, MygaCashFlowRecord, PolicyCashFlows
from ..models.policy import MygaPolicyState
from ..models.reinsurance import ReinsuranceTreaty

METHODOLOGY_VERSION = "yrt_v0.1.0"

_ZEROED_FIELDS = (
    "account_value_bop",
    "interest_credited",
    "partial_withdrawals",
    "surrender_charge",
    "mva_adjustment",
    "surrender_benefits",
    "maturity_benefits",
    "account_value_eop",
)


class YrtInput(BaseModel):
    """Inputs to the YRT engine."""

    treaty: ReinsuranceTreaty
    gross_cash_flows: GrossCashFlows | None = None
    policies: list[MygaPolicyState] = []  # provides death_benefit_basis per policy


class YrtOutput(BaseModel):
    """Output: ceded (death-only) and retained cash flow streams."""

    ceded_cash_flows: GrossCashFlows | None = None
    retained_cash_flows: GrossCashFlows | None = None


def calculate(inputs: YrtInput) -> YrtOutput:
    """Apply a YRT treaty to gross cash flows.

    Raises:
        ValueError: If the treaty is not YRT or ``gross_cash_flows`` is absent.
    """
    treaty = inputs.treaty
    if treaty.treaty_type is not ReinsuranceTreatyType.YRT:
        raise ValueError(
            f"Treaty {treaty.treaty_id} is {treaty.treaty_type.value}; "
            "the YRT engine handles YRT treaties only."
        )
    share = treaty.quota_share_pct if treaty.quota_share_pct is not None else 1.0
    if not 0.0 <= share <= 1.0:
        raise ValueError(
            f"Treaty {treaty.treaty_id} quota_share_pct={share} must be in [0, 1]."
        )
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "YrtInput.gross_cash_flows is required — run the projection "
            "engine (core.seriatim) first."
        )

    basis_by_policy = {p.policy_id: p.death_benefit_basis for p in inputs.policies}

    gross = inputs.gross_cash_flows
    ceded_policies: list[PolicyCashFlows] = []
    retained_policies: list[PolicyCashFlows] = []
    for policy_cf in gross.policies:
        # ROAV death benefits carry no net amount at risk — nothing cedes.
        has_nar = basis_by_policy.get(policy_cf.policy_id) == "ROP"
        ceded_records = []
        retained_records = []
        for record in policy_cf.records:
            ceded_death = share * record.death_benefits if has_nar else 0.0
            ceded_records.append(_death_only_record(record, ceded_death))
            retained_records.append(
                record.model_copy(
                    update={"death_benefits": record.death_benefits - ceded_death}
                )
            )
        ceded_policies.append(
            PolicyCashFlows(policy_id=policy_cf.policy_id, records=ceded_records)
        )
        retained_policies.append(
            PolicyCashFlows(policy_id=policy_cf.policy_id, records=retained_records)
        )

    return YrtOutput(
        ceded_cash_flows=GrossCashFlows(
            valuation_date=gross.valuation_date, policies=ceded_policies
        ),
        retained_cash_flows=GrossCashFlows(
            valuation_date=gross.valuation_date, policies=retained_policies
        ),
    )


def _death_only_record(
    record: MygaCashFlowRecord, ceded_death: float
) -> MygaCashFlowRecord:
    """Ceded record carrying only the ceded death benefit."""
    update: dict = {field: 0.0 for field in _ZEROED_FIELDS}
    update["death_benefits"] = ceded_death
    return record.model_copy(update=update)

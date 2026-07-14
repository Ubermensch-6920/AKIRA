"""
Apply reinsurance treaties to gross cash flows.

Routes each policy → treaty pairing to the appropriate treaty-type
engine (quota share in Phase 1; coinsurance / modco / FWH / YRT / XL in
Phase 2) and produces ceded and net cash flow streams suitable for
downstream framework reserving.

Pairing rule (Phase 1): each policy names at most one treaty via
``MygaPolicyState.reinsurance_treaty_id``. Policies with no treaty (or
with ``inputs.policies`` not supplied at all) are simply retained: they
appear in the net stream at gross and contribute nothing ceded.
"""

from pydantic import BaseModel

from ..assumptions.enums import ReinsuranceTreatyType
from ..assumptions.sets import AssumptionSet
from ..models.cash_flows import GrossCashFlows, PolicyCashFlows
from ..models.policy import MygaPolicyState
from ..models.reinsurance import ReinsuranceTreaty
from . import quota_share

METHODOLOGY_VERSION = "reinsurance_application_v0.1.0"


class ReinsuranceApplicationInput(BaseModel):
    """Inputs to the reinsurance application step."""

    assumption_set: AssumptionSet
    treaties: list[ReinsuranceTreaty]
    gross_cash_flows: GrossCashFlows | None = None
    policies: list[MygaPolicyState] = []  # provides the policy → treaty pairing


class ReinsuranceApplicationOutput(BaseModel):
    """Output: ceded + net cash flow streams keyed by policy / treaty."""

    ceded_cash_flows: GrossCashFlows | None = None
    net_cash_flows: GrossCashFlows | None = None


def calculate(inputs: ReinsuranceApplicationInput) -> ReinsuranceApplicationOutput:
    """Apply each treaty to its associated policies' gross cash flows.

    Returns ceded and net streams over the same valuation date as the
    gross input. The ceded stream carries one entry per reinsured policy;
    the net stream carries every policy (retained where reinsured, gross
    where not).

    Raises:
        ValueError: If ``gross_cash_flows`` is missing or a policy names
            a treaty_id not present in ``inputs.treaties``.
        NotImplementedError: If a paired treaty is a Phase 2 type
            (coinsurance / ModCo / FWH / YRT / XL).
    """
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "ReinsuranceApplicationInput.gross_cash_flows is required — "
            "run the projection engine (core.seriatim) first."
        )

    gross = inputs.gross_cash_flows
    treaty_by_id = {t.treaty_id: t for t in inputs.treaties}
    treaty_id_by_policy = {
        p.policy_id: p.reinsurance_treaty_id
        for p in inputs.policies
        if p.reinsurance_treaty_id is not None
    }

    ceded_policies: list[PolicyCashFlows] = []
    net_policies: list[PolicyCashFlows] = []

    for policy_cf in gross.policies:
        treaty_id = treaty_id_by_policy.get(policy_cf.policy_id)
        if treaty_id is None:
            net_policies.append(policy_cf)  # unreinsured: net == gross
            continue

        treaty = treaty_by_id.get(treaty_id)
        if treaty is None:
            raise ValueError(
                f"Policy {policy_cf.policy_id} references treaty "
                f"{treaty_id!r}, which is not in the supplied treaty list."
            )

        ceded_cf, retained_cf = _apply_treaty(treaty, policy_cf, gross)
        ceded_policies.append(ceded_cf)
        net_policies.append(retained_cf)

    return ReinsuranceApplicationOutput(
        ceded_cash_flows=GrossCashFlows(
            valuation_date=gross.valuation_date, policies=ceded_policies
        ),
        net_cash_flows=GrossCashFlows(
            valuation_date=gross.valuation_date, policies=net_policies
        ),
    )


def _apply_treaty(
    treaty: ReinsuranceTreaty,
    policy_cf: PolicyCashFlows,
    gross: GrossCashFlows,
) -> tuple[PolicyCashFlows, PolicyCashFlows]:
    """Route one policy's cash flows through its treaty-type engine."""
    if treaty.treaty_type is not ReinsuranceTreatyType.QUOTA_SHARE:
        raise NotImplementedError(
            f"Treaty {treaty.treaty_id} is {treaty.treaty_type.value}; "
            "Phase 1 supports QUOTA_SHARE only."
        )

    qs_output = quota_share.calculate(
        quota_share.QuotaShareInput(
            treaty=treaty,
            gross_cash_flows=GrossCashFlows(
                valuation_date=gross.valuation_date, policies=[policy_cf]
            ),
        )
    )
    assert qs_output.ceded_cash_flows and qs_output.retained_cash_flows
    return (
        qs_output.ceded_cash_flows.policies[0],
        qs_output.retained_cash_flows.policies[0],
    )

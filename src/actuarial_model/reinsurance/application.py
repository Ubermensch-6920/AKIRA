"""
Apply reinsurance treaties to gross cash flows.

Routes each treaty's policy group to the appropriate treaty-type engine
(quota share, coinsurance, ModCo, funds withheld, YRT, XL) and produces
ceded and net cash flow streams suitable for downstream framework
reserving.

Pairing rule: each policy names at most one treaty via
``MygaPolicyState.reinsurance_treaty_id``. Policies with no treaty (or
with ``inputs.policies`` not supplied at all) are simply retained: they
appear in the net stream at gross and contribute nothing ceded.

Treaties are applied at the treaty-group level — the whole group's cash
flows go to the engine in one call. Proportional structures are
indifferent to this, but XL requires it: the layer attaches on the
group's aggregate claims, not per policy.
"""

from pydantic import BaseModel

from ..assumptions.enums import ReinsuranceTreatyType
from ..assumptions.sets import AssumptionSet
from ..models.cash_flows import GrossCashFlows, PolicyCashFlows
from ..models.policy import MygaPolicyState
from ..models.reinsurance import ReinsuranceTreaty
from . import coinsurance, excess_of_loss, funds_withheld, modco, quota_share, yrt

METHODOLOGY_VERSION = "reinsurance_application_v0.2.0"


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
    """Apply each treaty to its policy group's gross cash flows.

    Returns ceded and net streams over the same valuation date as the
    gross input. The ceded stream carries one entry per reinsured policy;
    the net stream carries every policy (retained where reinsured, gross
    where not), preserving the input policy order.

    Raises:
        ValueError: If ``gross_cash_flows`` is missing, a policy names a
            treaty_id not present in ``inputs.treaties``, or a treaty's
            terms fail its engine's validation.
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

    # Group each reinsured policy's cash flows under its treaty.
    groups: dict[str, list[PolicyCashFlows]] = {}
    for policy_cf in gross.policies:
        treaty_id = treaty_id_by_policy.get(policy_cf.policy_id)
        if treaty_id is None:
            continue
        if treaty_id not in treaty_by_id:
            raise ValueError(
                f"Policy {policy_cf.policy_id} references treaty "
                f"{treaty_id!r}, which is not in the supplied treaty list."
            )
        groups.setdefault(treaty_id, []).append(policy_cf)

    ceded_by_policy: dict[str, PolicyCashFlows] = {}
    retained_by_policy: dict[str, PolicyCashFlows] = {}
    for treaty_id, group in groups.items():
        treaty = treaty_by_id[treaty_id]
        group_ids = {pcf.policy_id for pcf in group}
        group_policies = [p for p in inputs.policies if p.policy_id in group_ids]
        sub_gross = GrossCashFlows(valuation_date=gross.valuation_date, policies=group)
        ceded_cf, retained_cf = _apply_treaty(treaty, sub_gross, group_policies)
        for pcf in ceded_cf.policies:
            ceded_by_policy[pcf.policy_id] = pcf
        for pcf in retained_cf.policies:
            retained_by_policy[pcf.policy_id] = pcf

    # Assemble output streams in the original policy order.
    ceded_policies: list[PolicyCashFlows] = []
    net_policies: list[PolicyCashFlows] = []
    for policy_cf in gross.policies:
        if policy_cf.policy_id in ceded_by_policy:
            ceded_policies.append(ceded_by_policy[policy_cf.policy_id])
            net_policies.append(retained_by_policy[policy_cf.policy_id])
        else:
            net_policies.append(policy_cf)  # unreinsured: net == gross

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
    group_gross: GrossCashFlows,
    group_policies: list[MygaPolicyState],
) -> tuple[GrossCashFlows, GrossCashFlows]:
    """Route one treaty group's cash flows through its treaty-type engine."""
    if treaty.treaty_type is ReinsuranceTreatyType.QUOTA_SHARE:
        qs_out = quota_share.calculate(
            quota_share.QuotaShareInput(treaty=treaty, gross_cash_flows=group_gross)
        )
        return _require_streams(qs_out.ceded_cash_flows, qs_out.retained_cash_flows)
    if treaty.treaty_type is ReinsuranceTreatyType.COINSURANCE:
        coins_out = coinsurance.calculate(
            coinsurance.CoinsuranceInput(treaty=treaty, gross_cash_flows=group_gross)
        )
        return _require_streams(
            coins_out.ceded_cash_flows, coins_out.retained_cash_flows
        )
    if treaty.treaty_type is ReinsuranceTreatyType.MODCO:
        modco_out = modco.calculate(
            modco.ModcoInput(treaty=treaty, gross_cash_flows=group_gross)
        )
        return _require_streams(
            modco_out.ceded_cash_flows, modco_out.retained_cash_flows
        )
    if treaty.treaty_type is ReinsuranceTreatyType.FUNDS_WITHHELD:
        fwh_out = funds_withheld.calculate(
            funds_withheld.FundsWithheldInput(
                treaty=treaty, gross_cash_flows=group_gross
            )
        )
        return _require_streams(fwh_out.ceded_cash_flows, fwh_out.retained_cash_flows)
    if treaty.treaty_type is ReinsuranceTreatyType.YRT:
        yrt_out = yrt.calculate(
            yrt.YrtInput(
                treaty=treaty, gross_cash_flows=group_gross, policies=group_policies
            )
        )
        return _require_streams(yrt_out.ceded_cash_flows, yrt_out.retained_cash_flows)
    # EXCESS_OF_LOSS
    xl_out = excess_of_loss.calculate(
        excess_of_loss.ExcessOfLossInput(treaty=treaty, gross_cash_flows=group_gross)
    )
    return _require_streams(xl_out.ceded_cash_flows, xl_out.retained_cash_flows)


def _require_streams(
    ceded: GrossCashFlows | None, retained: GrossCashFlows | None
) -> tuple[GrossCashFlows, GrossCashFlows]:
    assert ceded is not None and retained is not None
    return ceded, retained

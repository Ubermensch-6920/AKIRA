"""
Excess-of-Loss (XL) reinsurance engine (Phase 2).

Annual-aggregate mortality XL on the treaty block: for each projection
year, the reinsurer covers aggregate death claims above
``xl_attachment`` up to ``xl_limit`` (the layer width). Recoveries are
allocated back to policies pro-rata to their death claims in the year,
producing per-policy ceded streams consistent with the rest of the
pipeline.

XL is inherently a block-level cover — unlike the proportional
structures it cannot be applied policy-by-policy, so the application
router passes the whole treaty group's cash flows in one call.

Phase 2 simplifications (documented for review):
  - Death claims only ("losses" = mortality); surrender runs are not
    covered (a lapse-XL variant would attach on surrender benefits).
  - The limit applies per projection year with free reinstatement — no
    aggregate-term limit or reinstatement premiums.
  - XL premiums are not modeled (no premium stream on the MYGA record).
"""

from collections import defaultdict

from pydantic import BaseModel

from ..assumptions.enums import ReinsuranceTreatyType
from ..models.cash_flows import GrossCashFlows, MygaCashFlowRecord, PolicyCashFlows
from ..models.reinsurance import ReinsuranceTreaty

METHODOLOGY_VERSION = "excess_of_loss_v0.1.0"

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


class ExcessOfLossInput(BaseModel):
    """Inputs to the XL engine."""

    treaty: ReinsuranceTreaty
    gross_cash_flows: GrossCashFlows | None = None


class ExcessOfLossOutput(BaseModel):
    """Output: ceded (layer recoveries) and retained cash flow streams."""

    ceded_cash_flows: GrossCashFlows | None = None
    retained_cash_flows: GrossCashFlows | None = None
    recoveries_by_year: dict[int, float] = {}  # projection year -> layer recovery


def calculate(inputs: ExcessOfLossInput) -> ExcessOfLossOutput:
    """Apply an annual-aggregate XL treaty to the block's gross cash flows.

    Raises:
        ValueError: If the treaty is not XL, ``xl_attachment`` /
            ``xl_limit`` are missing/invalid, or ``gross_cash_flows`` is
            absent.
    """
    treaty = inputs.treaty
    if treaty.treaty_type is not ReinsuranceTreatyType.EXCESS_OF_LOSS:
        raise ValueError(
            f"Treaty {treaty.treaty_id} is {treaty.treaty_type.value}; "
            "the XL engine handles EXCESS_OF_LOSS treaties only."
        )
    if treaty.xl_attachment is None or treaty.xl_attachment < 0.0:
        raise ValueError(
            f"Treaty {treaty.treaty_id} needs a non-negative xl_attachment."
        )
    if treaty.xl_limit is None or treaty.xl_limit <= 0.0:
        raise ValueError(f"Treaty {treaty.treaty_id} needs a positive xl_limit.")
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "ExcessOfLossInput.gross_cash_flows is required — run the "
            "projection engine (core.seriatim) first."
        )

    gross = inputs.gross_cash_flows
    valuation_date = gross.valuation_date

    # Aggregate block death claims by projection year.
    claims_by_year: dict[int, float] = defaultdict(float)
    for policy_cf in gross.policies:
        for record in policy_cf.records:
            year = _projection_year(valuation_date, record)
            claims_by_year[year] += record.death_benefits

    # Layer recovery per year, then a pro-rata ceded fraction of each
    # year's death claims.
    recoveries: dict[int, float] = {}
    ceded_fraction: dict[int, float] = {}
    for year, claims in claims_by_year.items():
        recovery = min(max(claims - treaty.xl_attachment, 0.0), treaty.xl_limit)
        if recovery > 0.0:
            recoveries[year] = recovery
            ceded_fraction[year] = recovery / claims

    ceded_policies: list[PolicyCashFlows] = []
    retained_policies: list[PolicyCashFlows] = []
    for policy_cf in gross.policies:
        ceded_records = []
        retained_records = []
        for record in policy_cf.records:
            fraction = ceded_fraction.get(_projection_year(valuation_date, record), 0.0)
            ceded_death = record.death_benefits * fraction
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

    return ExcessOfLossOutput(
        ceded_cash_flows=GrossCashFlows(
            valuation_date=valuation_date, policies=ceded_policies
        ),
        retained_cash_flows=GrossCashFlows(
            valuation_date=valuation_date, policies=retained_policies
        ),
        recoveries_by_year=dict(sorted(recoveries.items())),
    )


def _projection_year(valuation_date, record: MygaCashFlowRecord) -> int:
    """1-based projection year of a record's period-end date."""
    days = (record.period_end_date - valuation_date).days
    return max((days - 1) // 365 + 1, 1)


def _death_only_record(
    record: MygaCashFlowRecord, ceded_death: float
) -> MygaCashFlowRecord:
    """Ceded record carrying only the ceded death benefit."""
    update: dict = {field: 0.0 for field in _ZEROED_FIELDS}
    update["death_benefits"] = ceded_death
    return record.model_copy(update=update)

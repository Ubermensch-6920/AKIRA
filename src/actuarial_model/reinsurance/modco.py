"""
Modified Coinsurance (ModCo) reinsurance engine (Phase 2).

Coinsurance variant where the assets supporting the ceded reserves stay
with the cedent. Benefits split proportionally at ``coinsurance_pct``,
but the reinsurer's investment return comes through the ModCo interest
adjustment: each period the cedent credits ``modco_interest_rate`` on
the ceded reserve balance as part of the net settlement, in place of a
share of actual portfolio earnings. The ceded stream's
``interest_credited`` is therefore restated at the ModCo rate on the
ceded account value — it will not tie to the proportional share of the
gross crediting, which is the point of the structure.

Judgment area flagged (not modeled): when the ModCo interest is a
total-return pass-through of the cedent's portfolio, the arrangement
embeds a derivative under the old DIG B36 analysis — bifurcation at fair
value through income is not performed here; the exposure is surfaced in
``total_modco_interest`` for downstream assessment.

Phase 2 simplifications (documented for review):
  - Ceding commission / expense allowances are not modeled as cash flows.
  - Treaty effective / termination windows are not applied period-by-period.
"""

from pydantic import BaseModel

from ..assumptions.enums import ReinsuranceTreatyType
from ..models.cash_flows import GrossCashFlows, PolicyCashFlows
from ..models.reinsurance import ReinsuranceTreaty
from .proportional import split_proportional, validate_share

METHODOLOGY_VERSION = "modco_v0.1.0"


class ModcoInput(BaseModel):
    """Inputs to the ModCo engine."""

    treaty: ReinsuranceTreaty
    gross_cash_flows: GrossCashFlows | None = None


class ModcoOutput(BaseModel):
    """Output: ceded and retained cash flow streams."""

    ceded_cash_flows: GrossCashFlows | None = None
    retained_cash_flows: GrossCashFlows | None = None
    total_modco_interest: float = 0.0  # ModCo interest credited over the projection


def calculate(inputs: ModcoInput) -> ModcoOutput:
    """Apply a ModCo treaty to gross cash flows.

    Raises:
        ValueError: If the treaty is not ModCo, ``coinsurance_pct`` or
            ``modco_interest_rate`` is missing/invalid, or
            ``gross_cash_flows`` is absent.
    """
    treaty = inputs.treaty
    if treaty.treaty_type is not ReinsuranceTreatyType.MODCO:
        raise ValueError(
            f"Treaty {treaty.treaty_id} is {treaty.treaty_type.value}; "
            "the ModCo engine handles MODCO treaties only."
        )
    pct = validate_share(treaty.treaty_id, "coinsurance_pct", treaty.coinsurance_pct)
    if treaty.modco_interest_rate is None:
        raise ValueError(f"Treaty {treaty.treaty_id} has no modco_interest_rate.")
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "ModcoInput.gross_cash_flows is required — run the "
            "projection engine (core.seriatim) first."
        )

    ceded, retained = split_proportional(inputs.gross_cash_flows, pct)

    # Restate ceded interest at the ModCo rate on the ceded reserve balance.
    rate = treaty.modco_interest_rate
    total_modco_interest = 0.0
    restated_policies: list[PolicyCashFlows] = []
    for policy_cf in ceded.policies:
        restated = []
        for record in policy_cf.records:
            year_fraction = (
                record.period_end_date - record.period_start_date
            ).days / 365.25
            modco_interest = record.account_value_bop * (
                (1.0 + rate) ** year_fraction - 1.0
            )
            total_modco_interest += modco_interest
            restated.append(
                record.model_copy(update={"interest_credited": modco_interest})
            )
        restated_policies.append(
            PolicyCashFlows(policy_id=policy_cf.policy_id, records=restated)
        )

    return ModcoOutput(
        ceded_cash_flows=GrossCashFlows(
            valuation_date=ceded.valuation_date, policies=restated_policies
        ),
        retained_cash_flows=retained,
        total_modco_interest=total_modco_interest,
    )

"""
Funds-Withheld (FWH) reinsurance engine (Phase 2).

Coinsurance economics (proportional split at ``coinsurance_pct``) with
the assets held back by the cedent in a funds-withheld account that
credits ``funds_withheld_rate``. The FW account starts at the ceded
share of account value, accretes at the contractual rate, and pays down
as ceded benefits settle — its ending balance is the reinsurer's
receivable from (payable to) the cedent and drives collateral/credit
exposure between the parties.

Judgment area flagged (not modeled): like ModCo, a total-return FW
crediting rate embeds a derivative (DIG B36) — bifurcation is not
performed here; the FW balance path is surfaced for that assessment.

Phase 2 simplifications (documented for review):
  - FW crediting uses the flat contractual rate, not a portfolio
    total-return path.
  - Ceding commission / expense allowances are not modeled as cash flows.
  - Treaty effective / termination windows are not applied period-by-period.
"""

from pydantic import BaseModel

from ..assumptions.enums import ReinsuranceTreatyType
from ..models.cash_flows import GrossCashFlows
from ..models.reinsurance import ReinsuranceTreaty
from .proportional import split_proportional, validate_share

METHODOLOGY_VERSION = "funds_withheld_v0.1.0"


class FundsWithheldInput(BaseModel):
    """Inputs to the funds-withheld engine."""

    treaty: ReinsuranceTreaty
    gross_cash_flows: GrossCashFlows | None = None


class FundsWithheldOutput(BaseModel):
    """Output: ceded and retained cash flow streams plus the FW account."""

    ceded_cash_flows: GrossCashFlows | None = None
    retained_cash_flows: GrossCashFlows | None = None
    ending_fw_balance_by_policy: dict[str, float] = {}
    total_fw_interest: float = 0.0


def calculate(inputs: FundsWithheldInput) -> FundsWithheldOutput:
    """Apply a funds-withheld treaty to gross cash flows.

    Raises:
        ValueError: If the treaty is not funds-withheld,
            ``coinsurance_pct`` or ``funds_withheld_rate`` is
            missing/invalid, or ``gross_cash_flows`` is absent.
    """
    treaty = inputs.treaty
    if treaty.treaty_type is not ReinsuranceTreatyType.FUNDS_WITHHELD:
        raise ValueError(
            f"Treaty {treaty.treaty_id} is {treaty.treaty_type.value}; "
            "the funds-withheld engine handles FUNDS_WITHHELD treaties only."
        )
    pct = validate_share(treaty.treaty_id, "coinsurance_pct", treaty.coinsurance_pct)
    if treaty.funds_withheld_rate is None:
        raise ValueError(f"Treaty {treaty.treaty_id} has no funds_withheld_rate.")
    if inputs.gross_cash_flows is None:
        raise ValueError(
            "FundsWithheldInput.gross_cash_flows is required — run the "
            "projection engine (core.seriatim) first."
        )

    ceded, retained = split_proportional(inputs.gross_cash_flows, pct)

    # Roll the FW account per policy: seed at the ceded share of AV,
    # accrete at the contractual rate, pay down as ceded benefits settle.
    rate = treaty.funds_withheld_rate
    ending_balances: dict[str, float] = {}
    total_fw_interest = 0.0
    for policy_cf in ceded.policies:
        balance = policy_cf.records[0].account_value_bop if policy_cf.records else 0.0
        for record in policy_cf.records:
            year_fraction = (
                record.period_end_date - record.period_start_date
            ).days / 365.25
            fw_interest = balance * ((1.0 + rate) ** year_fraction - 1.0)
            total_fw_interest += fw_interest
            benefits = (
                record.death_benefits
                + record.surrender_benefits
                + record.partial_withdrawals
                + record.maturity_benefits
            )
            balance = balance + fw_interest - benefits
        ending_balances[policy_cf.policy_id] = balance

    return FundsWithheldOutput(
        ceded_cash_flows=ceded,
        retained_cash_flows=retained,
        ending_fw_balance_by_policy=ending_balances,
        total_fw_interest=total_fw_interest,
    )

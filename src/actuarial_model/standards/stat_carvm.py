"""
Pre-VM-22 CARVM (STAT) reserve calculation.

Implements Commissioner's Annuity Reserve Valuation Method per the
configured Actuarial Guideline (AG33 / AG35) with cash-flow-testing
overlay scenarios (Reg 126 or company).

Method (Phase 1):
  CARVM reserve = greatest present value of future *guaranteed* benefits.
  For a MYGA the candidate benefit at each future month m is the cash
  surrender value — guaranteed AV accumulated at ``guaranteed_rate`` less
  the surrender charge for that policy year — and, at the end of the
  guarantee period, the full account value (no charge). Each candidate is
  discounted at the statutory valuation rate; the reserve is the maximum.
  Evaluating at t=0 makes the current CSV a natural floor.

  Unlike BEL, no best-estimate lapse or mortality assumptions enter the
  calculation: CARVM assumes the policyholder elects the benefit pattern
  most costly to the insurer.

Phase 1 simplifications (documented for review):
  - Elective benefits only (CSV / maturity). AG33 integrated streams with
    mortality-weighted death benefits are not yet overlaid; for ROAV death
    benefits this understates the reserve only marginally.
  - Free-partial-withdrawal corridors are not exercised as elective options.
  - No CFT (Reg 126) scenario overlay yet — single deterministic path.
"""

import calendar
from datetime import date

from pydantic import BaseModel

from ..assumptions.enums import Framework
from ..assumptions.sets import AssumptionSet
from ..models.cash_flows import GrossCashFlows
from ..models.policy import MygaPolicyState
from ..models.results import ReserveResult, ResultMetadata
from ..withdrawal.rates import SurrenderChargeRepository, SurrenderChargeSchedule
from .bel import _aggregate_labels

METHODOLOGY_VERSION = "stat_carvm_v0.1.0"

_SURRENDER_REPO = SurrenderChargeRepository.with_athene_schedules()


class StatCarvmInput(BaseModel):
    """Inputs to the STAT (CARVM) reserve calculation."""

    assumption_set: AssumptionSet
    gross_cash_flows: GrossCashFlows | None = None
    policies: list[MygaPolicyState] = []
    valuation_date: date | None = None
    run_id: str = ""


class StatCarvmOutput(BaseModel):
    """Output of the STAT (CARVM) reserve calculation."""

    reserve_result: ReserveResult


class PolicyCarvmDetail(BaseModel):
    """Per-policy CARVM decomposition for audit / debugging."""

    policy_id: str
    reserve: float
    csv_at_valuation: float
    greatest_pv_month: int  # months from valuation date; 0 == current CSV governs
    months_to_maturity: int


def calculate(inputs: StatCarvmInput) -> StatCarvmOutput:
    """Compute Pre-VM-22 CARVM reserves for every policy in ``inputs.policies``.

    The reserve works directly from guaranteed policy terms, so
    ``gross_cash_flows`` (best-estimate projection) is not consumed here —
    it is reserved for the future CFT overlay.
    """
    config = inputs.assumption_set.stat_carvm
    i_val = config.valuation_interest_rate

    valuation_date = inputs.valuation_date or (
        inputs.policies[0].valuation_date if inputs.policies else date.today()
    )

    details: list[PolicyCarvmDetail] = []
    for policy in inputs.policies:
        schedule = _resolve_surrender_schedule(policy)
        details.append(
            _policy_carvm_reserve(policy, schedule, i_val, valuation_date)
        )

    gross_reserve = sum(d.reserve for d in details)
    legal_entity, segment, cohort_id = _aggregate_labels(inputs.policies)

    result = ReserveResult(
        metadata=ResultMetadata(
            valuation_date=valuation_date,
            framework=Framework.STAT_CARVM,
            methodology_version=METHODOLOGY_VERSION,
            run_id=inputs.run_id,
            assumption_set_id=inputs.assumption_set.assumption_set_id,
        ),
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        gross_reserve=gross_reserve,
        ceded_reserve=0.0,  # Phase 1: reinsurance not yet applied
        net_reserve=gross_reserve,
        components={
            "carvm_basis": config.carvm_basis.value,
            "valuation_interest_rate": i_val,
            "policy_count": len(details),
            "policy_detail": {d.policy_id: d.model_dump() for d in details},
        },
    )
    return StatCarvmOutput(reserve_result=result)


def _policy_carvm_reserve(
    policy: MygaPolicyState,
    schedule: SurrenderChargeSchedule | None,
    i_val: float,
    valuation_date: date,
) -> PolicyCarvmDetail:
    """Greatest present value of guaranteed CSV / maturity benefits.

    Walks month by month from the valuation date to the end of the
    guarantee period. The account value accumulates at the guaranteed
    rate; the benefit at each month is AV net of that policy year's
    surrender charge (full AV at maturity).
    """
    months_to_maturity = _months_between(valuation_date, policy.guarantee_end_date)

    # Matured or maturing policy: reserve is the full account value.
    if months_to_maturity <= 0:
        return PolicyCarvmDetail(
            policy_id=policy.policy_id,
            reserve=policy.account_value,
            csv_at_valuation=policy.account_value,
            greatest_pv_month=0,
            months_to_maturity=0,
        )

    monthly_growth = (1.0 + policy.guaranteed_rate) ** (1.0 / 12.0)
    monthly_discount = (1.0 + i_val) ** (-1.0 / 12.0)

    # t = 0: current CSV is the floor.
    csv_now = policy.account_value * (
        1.0 - _surrender_charge_rate(policy, schedule, valuation_date)
    )
    best_pv = csv_now
    best_month = 0

    av = policy.account_value
    df = 1.0
    for month in range(1, months_to_maturity + 1):
        av *= monthly_growth
        df *= monthly_discount
        benefit_date = _add_months(valuation_date, month)

        if month == months_to_maturity:
            benefit = av  # maturity: full AV, no surrender charge
        else:
            sc_rate = _surrender_charge_rate(policy, schedule, benefit_date)
            benefit = av * (1.0 - sc_rate)

        pv = benefit * df
        if pv > best_pv:
            best_pv = pv
            best_month = month

    return PolicyCarvmDetail(
        policy_id=policy.policy_id,
        reserve=best_pv,
        csv_at_valuation=csv_now,
        greatest_pv_month=best_month,
        months_to_maturity=months_to_maturity,
    )


def _surrender_charge_rate(
    policy: MygaPolicyState,
    schedule: SurrenderChargeSchedule | None,
    as_of: date,
) -> float:
    """Surrender charge rate in effect on ``as_of`` (policy-year lookup)."""
    if schedule is None:
        return 0.0
    policy_year = _months_between(policy.issue_date, as_of) // 12 + 1
    return schedule.charge_at_year(policy_year)


def _resolve_surrender_schedule(
    policy: MygaPolicyState,
) -> SurrenderChargeSchedule | None:
    """Embedded-repository lookup; unknown IDs mean no surrender charges."""
    try:
        return _SURRENDER_REPO.get(policy.surrender_charge_schedule_id)
    except ValueError:
        return None


def _months_between(start: date, end: date) -> int:
    """Whole calendar months from ``start`` to ``end``."""
    return (end.year - start.year) * 12 + (end.month - start.month)


def _add_months(anchor: date, months: int) -> date:
    """``anchor`` shifted forward by ``months`` calendar months (day clamped)."""
    total = anchor.month - 1 + months
    year = anchor.year + total // 12
    month = total % 12 + 1
    # Clamp the day for short months (e.g. Jan 31 + 1 month -> Feb 28).
    day = min(anchor.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]

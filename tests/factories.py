"""Shared builders for engine / basis tests."""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta

from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.bases.common import RunStamp
from actuarial_model.engine.curves import CurvePoint
from actuarial_model.engine.grid import year_fraction
from actuarial_model.models.policy import MygaPolicyState

VAL_DATE = date(2025, 1, 1)


def assumption_set(set_id: str = "as-test") -> AssumptionSet:
    return AssumptionSet(
        assumption_set_id=set_id,
        version="0.1.0",
        description="test",
        created_by="pytest",
        created_date=VAL_DATE,
    )


def stamp(run_id: str = "RUN-1", set_id: str = "as-test") -> RunStamp:
    return RunStamp(valuation_date=VAL_DATE, run_id=run_id, assumption_set_id=set_id)


def flat_curve(rate: float) -> list[CurvePoint]:
    return [CurvePoint(tenor_years=1.0, rate=rate), CurvePoint(tenor_years=30.0, rate=rate)]


def payment_tenor(period: int, valuation_date: date = VAL_DATE) -> float:
    """Tenor (years) of a cash flow paid at the end of 0-based ``period``."""
    return year_fraction(valuation_date, valuation_date + relativedelta(months=period + 1))


def policy(
    policy_id: str = "P1",
    *,
    account_value: float = 100_000.0,
    single_premium: float | None = None,
    guaranteed_rate: float = 0.03,
    guarantee_period_years: int = 5,
    issue_date: date = VAL_DATE,
    issue_age: int = 60,
    sex: str = "M",
    surrender_charge_schedule_id: str = "NONE",  # unknown ID -> no charges
    death_benefit_basis: str = "ROAV",
    free_withdrawal_pct: float = 0.10,
    legal_entity: str = "ENT-A",
    segment: str = "MYGA-RETAIL",
    cohort_id: str = "2025Q1",
    reinsurance_treaty_id: str | None = None,
) -> MygaPolicyState:
    return MygaPolicyState(
        policy_id=policy_id,
        issue_date=issue_date,
        issue_age=issue_age,
        sex=sex,
        issue_state="NY",
        legal_entity=legal_entity,
        segment=segment,
        cohort_id=cohort_id,
        valuation_date=VAL_DATE,
        single_premium=account_value if single_premium is None else single_premium,
        account_value=account_value,
        guaranteed_rate=guaranteed_rate,
        guarantee_period_years=guarantee_period_years,
        guarantee_end_date=issue_date + relativedelta(years=guarantee_period_years),
        surrender_charge_schedule_id=surrender_charge_schedule_id,
        death_benefit_basis=death_benefit_basis,
        free_withdrawal_pct=free_withdrawal_pct,
        reinsurance_treaty_id=reinsurance_treaty_id,
    )

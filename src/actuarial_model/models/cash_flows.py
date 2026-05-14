"""
Per-policy and aggregate cash-flow containers.

:class:`MygaCashFlowRecord` represents one projection period for one policy.
:class:`PolicyCashFlows` collects all periods for a single policy.
:class:`GrossCashFlows` aggregates across all policies in a valuation run and
serves as the typed payload passed between the projection engine, reinsurance
application, BEL discounting, and every framework reserve module.
"""

from datetime import date

from pydantic import BaseModel


class MygaCashFlowRecord(BaseModel):
    """Per-period, per-policy MYGA cash-flow record."""

    policy_id: str
    period: int
    period_start_date: date
    period_end_date: date
    account_value_bop: float
    interest_credited: float
    partial_withdrawals: float
    surrender_charge: float
    mva_adjustment: float
    surrender_benefits: float
    death_benefits: float
    account_value_eop: float
    lives_in_force: float  # surviving fraction after mortality + lapse decrements


class PolicyCashFlows(BaseModel):
    """All projection-period cash flows for a single policy."""

    policy_id: str
    records: list[MygaCashFlowRecord]


class GrossCashFlows(BaseModel):
    """Aggregated gross cash flows across all policies in a run."""

    valuation_date: date
    policies: list[PolicyCashFlows]

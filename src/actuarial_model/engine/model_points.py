"""
Seriatim policy records → a gaspatchio model-point frame.

One row per policy, scalar columns only. Timing fields the projection needs
are resolved here once per policy (O(policies)), so the gaspatchio model
itself is pure vector arithmetic over the grid.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from ..models.policy import MygaPolicyState
from .grid import add_months, months_between

MODEL_POINT_SCHEMA: dict[str, pl.DataType] = {
    "policy_id": pl.String(),
    "legal_entity": pl.String(),
    "segment": pl.String(),
    "cohort_id": pl.String(),
    "sex": pl.String(),
    "issue_age": pl.Int64(),
    "issue_date": pl.Date(),
    "single_premium": pl.Float64(),
    "account_value": pl.Float64(),
    "guaranteed_rate": pl.Float64(),
    "guarantee_period_years": pl.Int64(),
    "guarantee_end_date": pl.Date(),
    "surrender_charge_schedule_id": pl.String(),
    "death_benefit_basis": pl.String(),
    "free_withdrawal_pct": pl.Float64(),
    "reinsurance_treaty_id": pl.String(),
    # Resolved timing (relative to the run valuation date)
    "duration_months_at_valuation": pl.Int64(),
    "days_since_issue_at_valuation": pl.Float64(),
    "maturity_period": pl.Int64(),
    "months_to_maturity": pl.Int64(),
}


def maturity_period(valuation_date, guarantee_end_date) -> int:
    """0-based period in which the guarantee ends (first period whose end >= GED)."""
    t = max(months_between(valuation_date, guarantee_end_date) - 1, 0)
    while add_months(valuation_date, t + 1) < guarantee_end_date:
        t += 1
    while t > 0 and add_months(valuation_date, t) >= guarantee_end_date:
        t -= 1
    return t


def myga_model_points(policies: Sequence[MygaPolicyState], valuation_date) -> pl.DataFrame:
    """Build the MYGA model-point frame for projection from ``valuation_date``."""
    rows = [
        {
            "policy_id": p.policy_id,
            "legal_entity": p.legal_entity,
            "segment": p.segment,
            "cohort_id": p.cohort_id,
            "sex": p.sex,
            "issue_age": p.issue_age,
            "issue_date": p.issue_date,
            "single_premium": p.single_premium,
            "account_value": p.account_value,
            "guaranteed_rate": p.guaranteed_rate,
            "guarantee_period_years": p.guarantee_period_years,
            "guarantee_end_date": p.guarantee_end_date,
            "surrender_charge_schedule_id": p.surrender_charge_schedule_id,
            "death_benefit_basis": p.death_benefit_basis,
            "free_withdrawal_pct": p.free_withdrawal_pct,
            "reinsurance_treaty_id": p.reinsurance_treaty_id,
            "duration_months_at_valuation": months_between(p.issue_date, valuation_date),
            "days_since_issue_at_valuation": float((valuation_date - p.issue_date).days),
            "maturity_period": maturity_period(valuation_date, p.guarantee_end_date),
            "months_to_maturity": months_between(valuation_date, p.guarantee_end_date),
        }
        for p in policies
    ]
    return pl.DataFrame(rows, schema=MODEL_POINT_SCHEMA)

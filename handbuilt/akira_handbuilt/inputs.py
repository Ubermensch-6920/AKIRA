"""
Data plumbing for the hand-built engine (AI-assisted).

Nothing actuarial is decided here: this module turns seriatim records and
assumption tables into NumPy arrays, and turns the finished cash-flow arrays
back into the :class:`Projection` frame every basis consumes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import polars as pl

from actuarial_model.assumptions.mortality import MortalityAssumptionRepository
from actuarial_model.assumptions.sets import MortalityConfig
from actuarial_model.assumptions.withdrawal import SurrenderChargeRepository
from actuarial_model.engine.grid import DAYS_PER_YEAR, ProjectionGrid
from actuarial_model.engine.model_points import myga_model_points
from actuarial_model.engine.projection import (
    CASH_FLOW_COLUMNS,
    COUNT_COLUMNS,
    LABEL_COLUMNS,
    Projection,
)
from actuarial_model.models.policy import MygaPolicyState

MAX_AGE = 130

_MORTALITY_REPO = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
_SURRENDER_REPO = SurrenderChargeRepository.with_athene_schedules()


@dataclass(frozen=True)
class PolicyArrays:
    """One NumPy array per model-point field, all shaped (P,)."""

    labels: pl.DataFrame  # policy_id, legal_entity, segment, cohort_id, reinsurance_treaty_id
    sex: np.ndarray  # str
    issue_age: np.ndarray  # int
    account_value: np.ndarray
    single_premium: np.ndarray
    guaranteed_rate: np.ndarray
    free_withdrawal_pct: np.ndarray
    death_benefit_is_rop: np.ndarray  # bool
    surrender_charge_schedule_id: np.ndarray  # str
    duration_months_at_valuation: np.ndarray  # int
    days_since_issue_at_valuation: np.ndarray
    maturity_period: np.ndarray  # int, 0-based period the guarantee ends in

    @property
    def n_policies(self) -> int:
        return len(self.issue_age)


def policy_arrays(policies: Sequence[MygaPolicyState], valuation_date: date) -> PolicyArrays:
    mp = myga_model_points(policies, valuation_date)
    return PolicyArrays(
        labels=mp.select(*LABEL_COLUMNS, "reinsurance_treaty_id"),
        sex=mp["sex"].to_numpy(),
        issue_age=mp["issue_age"].to_numpy(),
        account_value=mp["account_value"].to_numpy(),
        single_premium=mp["single_premium"].to_numpy(),
        guaranteed_rate=mp["guaranteed_rate"].to_numpy(),
        free_withdrawal_pct=mp["free_withdrawal_pct"].to_numpy(),
        death_benefit_is_rop=(mp["death_benefit_basis"] == "ROP").to_numpy(),
        surrender_charge_schedule_id=mp["surrender_charge_schedule_id"].to_numpy(),
        duration_months_at_valuation=mp["duration_months_at_valuation"].to_numpy(),
        days_since_issue_at_valuation=mp["days_since_issue_at_valuation"].to_numpy(),
        maturity_period=mp["maturity_period"].to_numpy(),
    )


def mortality_rates(
    config: MortalityConfig,
    sex: np.ndarray,
    attained_age: np.ndarray,
    repository: MortalityAssumptionRepository = _MORTALITY_REPO,
) -> tuple[np.ndarray, np.ndarray]:
    """(base annual qx, G2 improvement rate), both (P, T), by sex and attained age."""

    def dense(table_ids: Mapping[str, str]) -> np.ndarray:
        # rows: one per policy's sex; columns: ages 0..MAX_AGE (table ends clamped)
        by_sex = {
            s: np.array([repository.get(table_ids[s]).rate_at_age(a) for a in range(MAX_AGE + 1)])
            for s in set(sex.tolist())
        }
        return np.stack([by_sex[s] for s in sex]) if len(sex) else np.empty((0, MAX_AGE + 1))

    rows = np.arange(len(sex))[:, None]
    base = dense(config.base_table_id_by_sex)[rows, attained_age]
    g2 = dense(config.improvement_table_id_by_sex)[rows, attained_age]
    return base, g2


def improvement_clocks(
    grid: ProjectionGrid,
    config: MortalityConfig,
    days_since_issue_at_valuation: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """(years since G2 base date (T,), years since issue (P, T)) at each period start, floored at 0."""
    years_since_g2 = np.maximum(np.array(grid.years_since(config.g2_base_date)), 0.0)
    days_from_val = np.array(grid.days_from_valuation())
    years_since_issue = np.maximum(
        (days_from_val[None, :] + days_since_issue_at_valuation[:, None]) / DAYS_PER_YEAR, 0.0
    )
    return years_since_g2, years_since_issue


def surrender_charge_rates(
    schedule_ids: np.ndarray,
    policy_year: np.ndarray,
    repository: SurrenderChargeRepository = _SURRENDER_REPO,
) -> np.ndarray:
    """Surrender charge rate (P, T); 0 for unknown schedules or years past the charge period."""
    out = np.zeros(policy_year.shape)
    for i, schedule_id in enumerate(schedule_ids):
        try:
            schedule = repository.get(schedule_id)
        except ValueError:
            continue
        out[i] = [schedule.charge_at_year(int(y)) for y in policy_year[i]]
    return out


def to_projection(
    grid: ProjectionGrid,
    labels: pl.DataFrame,
    cash_flows: Mapping[str, np.ndarray],
    methodology_version: str,
) -> Projection:
    """Pack (P, T) cash-flow arrays into the Projection frame the bases consume."""
    missing = set(CASH_FLOW_COLUMNS + COUNT_COLUMNS) - set(cash_flows)
    if missing:
        raise ValueError(f"cash_flows is missing columns: {sorted(missing)}")
    frame = labels.with_columns(
        pl.Series(name, cash_flows[name].tolist(), dtype=pl.List(pl.Float64()))
        for name in CASH_FLOW_COLUMNS + COUNT_COLUMNS
    )
    return Projection(grid=grid, frame=frame, methodology_version=methodology_version)

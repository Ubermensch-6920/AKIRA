"""
AKIRA assumption config → gaspatchio ``Table`` objects.

gaspatchio registers tables globally by name and resolves lookups by name at
execution time; re-registering a name with different data supersedes the
earlier table. Every table built here is therefore *content-addressed* — its
name carries a hash of its data — so two bases with different lapse
assumptions can never read each other's rates, and identical assumptions
share one registration.
"""

from __future__ import annotations

import hashlib
import json

import polars as pl
from gaspatchio.assumptions import Table

from ..assumptions.mortality import MortalityAssumptionRepository, RateTable
from ..assumptions.sets import MortalityConfig
from ..assumptions.withdrawal import SurrenderChargeRepository

MAX_TABLE_AGE = 130  # attained ages are clipped to [0, MAX_TABLE_AGE] before lookup

_SEXES = ("M", "F", "U")


def _content_name(prefix: str, payload: object) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return f"akira_{prefix}_{digest[:16]}"


def _dense_age_rates(table: RateTable) -> list[float]:
    """Rates for ages 0..MAX_TABLE_AGE, clamping to the table's own age range."""
    return [table.rate_at_age(age) for age in range(MAX_TABLE_AGE + 1)]


def _sex_age_table(
    prefix: str,
    table_id_by_sex: dict[str, str],
    repository: MortalityAssumptionRepository,
) -> Table:
    ages = list(range(MAX_TABLE_AGE + 1))
    sex_col: list[str] = []
    age_col: list[int] = []
    rate_col: list[float] = []
    for sex in _SEXES:
        rates = _dense_age_rates(repository.get(table_id_by_sex[sex]))
        sex_col.extend([sex] * len(ages))
        age_col.extend(ages)
        rate_col.extend(rates)
    source = pl.DataFrame({"sex": sex_col, "age": age_col, "rate": rate_col})
    return Table(
        name=_content_name(prefix, {"sex": sex_col, "age": age_col, "rate": rate_col}),
        source=source,
        dimensions={"sex": "sex", "age": "age"},
        value="rate",
    )


def mortality_tables(
    config: MortalityConfig,
    repository: MortalityAssumptionRepository,
) -> tuple[Table, Table]:
    """(base annual qx, G2 improvement rate) tables keyed by sex and attained age."""
    base = _sex_age_table("mort_base", config.base_table_id_by_sex, repository)
    improvement = _sex_age_table("mort_g2", config.improvement_table_id_by_sex, repository)
    return base, improvement


def policy_year_table(prefix: str, rates_by_year: dict[int, float], default: float) -> Table | None:
    """Annual rate by policy year with ``default`` for unlisted years.

    Returns ``None`` when no year overrides the default — callers then use
    the scalar default directly.
    """
    if not rates_by_year:
        return None
    years = sorted(rates_by_year)
    rates = [rates_by_year[y] for y in years]
    return Table(
        name=_content_name(prefix, {"years": years, "rates": rates, "default": default}),
        source=pl.DataFrame({"policy_year": years, "rate": rates}),
        dimensions={"policy_year": "policy_year"},
        value="rate",
        on_missing=default,
    )


def surrender_charge_table(repository: SurrenderChargeRepository) -> Table:
    """Surrender charge rate by (schedule id, policy year); 0 when not listed.

    Unknown schedule IDs and years past the charge period both return 0.
    """
    schedule_ids: list[str] = []
    years: list[int] = []
    rates: list[float] = []
    for schedule_id in sorted(repository.list_schedules()):
        schedule = repository.get(schedule_id)
        for year, rate in sorted(schedule.charges_by_year.items()):
            schedule_ids.append(schedule_id)
            years.append(year)
            rates.append(rate)
    return Table(
        name=_content_name("surrender", {"ids": schedule_ids, "years": years, "rates": rates}),
        source=pl.DataFrame(
            {"surrender_charge_schedule_id": schedule_ids, "policy_year": years, "rate": rates}
        ),
        dimensions={
            "surrender_charge_schedule_id": "surrender_charge_schedule_id",
            "policy_year": "policy_year",
        },
        value="rate",
        on_missing=0.0,
    )

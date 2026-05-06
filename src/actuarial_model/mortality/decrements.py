from __future__ import annotations

from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Literal
import re
import urllib.request
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from actuarial_model.lapse import LapseRateTable
from actuarial_model.withdrawal import WithdrawalCalculator


# =============================================================================
# AKIRA mortality decrement engine
# =============================================================================
#
# Purpose:
#   Standalone mortality decrement calculator for early AKIRA development.
#
# Current scope:
#   - Single life and joint life
#   - Monthly / quarterly / annual projections
#   - SOA 2012 IAM Basic base mortality, table IDs 2581 and 2582
#   - G2 projection scale / mortality improvement factor, table ID 2583
#   - Additional flat mortality improvement overlay, e.g. 1% per year
#   - Placeholder lapse and maturity decrements fixed to 0
#
# Key formula:
#   adjusted_annual_qx =
#       base_qx
#       * mortality_multiplier
#       * (1 - g2_rate * g2_scale_multiplier) ** years_since_g2_base_date
#       * (1 - flat_improvement_rate) ** years_since_flat_improvement_base_date
#
# Notes:
#   - SOA table 2581 = 2012 IAM Basic Male, ANB.
#   - SOA table 2582 = 2012 IAM Basic Female, ANB.
#   - SOA table 2583 = Projection Scale G2 Male, ANB.
#   - This file embeds those table values for reproducible local development.
#   - The repository/loader plumbing is intentionally separated so a future
#     controller can swap embedded, URL-based, or file-based assumptions.
# =============================================================================


class ProjectionFrequency(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"

    @property
    def periods_per_year(self) -> int:
        if self is ProjectionFrequency.MONTHLY:
            return 12
        if self is ProjectionFrequency.QUARTERLY:
            return 4
        return 1

    @property
    def years_per_period(self) -> float:
        return 1.0 / self.periods_per_year

    @property
    def months_per_period(self) -> int:
        return 12 // self.periods_per_year


class MortalityMethod(str, Enum):
    CONSTANT_FORCE = "constant_force"
    UDD = "udd"


class LifeStatus(str, Enum):
    SINGLE = "single_life"
    JOINT = "joint_life"


class Sex(str, Enum):
    MALE = "M"
    FEMALE = "F"
    UNISEX = "U"


class TableSourceKind(str, Enum):
    EMBEDDED = "embedded"
    SOA_URL = "soa_url"
    CSV_FILE = "csv_file"


class RateTable(BaseModel):
    """One-dimensional annual age-indexed rate table."""

    table_id: str
    description: str = ""
    rates_by_age: dict[int, float]
    source: str = "unknown"

    @field_validator("rates_by_age")
    @classmethod
    def validate_rates_by_age(cls, value: dict[int, float]) -> dict[int, float]:
        if not value:
            raise ValueError("rates_by_age must not be empty.")

        cleaned: dict[int, float] = {}
        for age, rate in value.items():
            age_int = int(age)
            rate_float = float(rate)
            if age_int < 0:
                raise ValueError("Table ages must be non-negative.")
            if rate_float < 0.0 or rate_float > 1.0:
                raise ValueError("Rates must be between 0 and 1.")
            cleaned[age_int] = rate_float

        return dict(sorted(cleaned.items()))

    @property
    def min_age(self) -> int:
        return min(self.rates_by_age)

    @property
    def max_age(self) -> int:
        return max(self.rates_by_age)

    def rate_at_age(self, attained_age: float) -> float:
        integer_age = int(np.floor(attained_age))
        table_age = min(max(integer_age, self.min_age), self.max_age)
        return float(self.rates_by_age[table_age])


class AssumptionSelection(BaseModel):
    """Controller-facing assumption selector.

    This object is deliberately passed into the calculator rather than hardcoded.

    `base_table_id_by_sex` lets the controller decide which base table a life uses.
    `improvement_table_id_by_sex` lets the controller decide which improvement
    scale applies. In this build both sexes default to 2583 because that was the
    requested G2 source. You can later switch F to 2584 if desired.
    """

    assumption_set_id: str = "DEV_SOA_IAM_G2_2021"
    base_table_id_by_sex: dict[Sex, str] = Field(
        default_factory=lambda: {
            Sex.MALE: "SOA_2012_IAM_BASIC_MALE_2581",
            Sex.FEMALE: "SOA_2012_IAM_BASIC_FEMALE_2582",
            Sex.UNISEX: "SOA_2012_IAM_BASIC_MALE_2581",
        }
    )
    improvement_table_id_by_sex: dict[Sex, str] = Field(
        default_factory=lambda: {
            Sex.MALE: "SOA_G2_MALE_2583",
            Sex.FEMALE: "SOA_G2_MALE_2583",
            Sex.UNISEX: "SOA_G2_MALE_2583",
        }
    )
    mortality_multiplier: float = Field(default=1.0, gt=0.0)
    g2_scale_multiplier: float = Field(default=1.0, ge=0.0)
    flat_improvement_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    lapse_rate_table: LapseRateTable | None = None
    withdrawal_assumptions: Any | None = None
    creditor_config: Any | None = None

    # 2012 IAM Basic rates are presented as a 2012 table. This is used to
    # improve base mortality to the projection period.
    g2_base_date: date = date(2012, 1, 1)

    # Additional flat MI overlay starts from issue date by default. The controller
    # can override this date for a valuation basis or stress basis.
    flat_improvement_base_date: date | None = None


class SeriatimLifeInput(BaseModel):
    """Controller-facing seriatim life input."""

    life_id: str
    issue_age: float = Field(ge=0.0, le=130.0)
    sex: Sex


class SeriatimPolicyInput(BaseModel):
    """Controller-facing policy-level seriatim input.

    For Phase 1, issue date is the projection start date.
    """

    policy_id: str
    issue_date: date
    lives: list[SeriatimLifeInput] = Field(min_length=1, max_length=2)
    starting_policy_count: float = Field(default=1.0, ge=0.0)

    @property
    def basis(self) -> LifeStatus:
        return LifeStatus.SINGLE if len(self.lives) == 1 else LifeStatus.JOINT


class MortalityProjectionRequest(BaseModel):
    """Full calculator request after controller passthrough."""

    seriatim: SeriatimPolicyInput
    assumptions: AssumptionSelection
    projection_periods: int = Field(gt=0)
    frequency: ProjectionFrequency = ProjectionFrequency.MONTHLY
    method: MortalityMethod = MortalityMethod.CONSTANT_FORCE
    run_id: str = "DEV_RUN"


class MortalityProjectionRow(BaseModel):
    period: int
    period_start_date: date
    period_end_date: date
    projection_year: float
    frequency: ProjectionFrequency

    run_id: str
    policy_id: str
    assumption_set_id: str
    basis: LifeStatus
    methodology_version: str

    attained_age_1: float
    base_annual_qx_1: float
    g2_rate_1: float
    adjusted_annual_qx_1: float
    period_qx_1: float

    attained_age_2: float | None = None
    base_annual_qx_2: float | None = None
    g2_rate_2: float | None = None
    adjusted_annual_qx_2: float | None = None
    period_qx_2: float | None = None

    single_inforce_start: float | None = None
    single_mortality_decrement: float | None = None
    single_lapse_decrement: float = 0.0
    single_withdrawal_decrement: float = 0.0
    single_maturity_decrement: float = 0.0
    single_crediting_accrual: float = 0.0
    single_inforce_end: float | None = None

    both_alive_start: float | None = None
    life1_only_alive_start: float | None = None
    life2_only_alive_start: float | None = None
    all_dead_start: float | None = None

    life1_mortality_decrement: float | None = None
    life2_mortality_decrement: float | None = None
    joint_first_death_decrement: float | None = None
    joint_last_survivor_decrement: float | None = None
    joint_lapse_decrement: float = 0.0
    joint_withdrawal_decrement: float = 0.0
    joint_maturity_decrement: float = 0.0
    joint_crediting_accrual: float = 0.0

    both_alive_end: float | None = None
    life1_only_alive_end: float | None = None
    life2_only_alive_end: float | None = None
    all_dead_end: float | None = None
    joint_first_death_inforce_end: float | None = None
    joint_last_survivor_inforce_end: float | None = None


class MortalityProjectionOutput(BaseModel):
    run_id: str
    policy_id: str
    assumption_set_id: str
    basis: LifeStatus
    frequency: ProjectionFrequency
    projection_periods: int
    issue_date: date
    methodology_version: str
    records: list[MortalityProjectionRow]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([record.model_dump(mode="json") for record in self.records])


class MortalityAssumptionRepository:
    """Repository for base mortality and improvement scale tables.

    Current build supports:
      - embedded SOA tables
      - CSV files with columns: age, rate
      - URL fetch plumbing for SOA pages / XML, with embedded fallback recommended
    """

    def __init__(self, tables: dict[str, RateTable] | None = None) -> None:
        self._tables = tables or {}

    @classmethod
    def with_embedded_soa_iam_g2(cls) -> "MortalityAssumptionRepository":
        return cls(
            {
                "SOA_2012_IAM_BASIC_MALE_2581": RateTable(
                    table_id="SOA_2012_IAM_BASIC_MALE_2581",
                    description="2012 IAM Basic Table - Male, ANB, SOA Table Identity 2581",
                    rates_by_age=_embedded_soa_2012_iam_basic_male_2581(),
                    source="embedded_from_soa_table_2581",
                ),
                "SOA_2012_IAM_BASIC_FEMALE_2582": RateTable(
                    table_id="SOA_2012_IAM_BASIC_FEMALE_2582",
                    description="2012 IAM Basic Table - Female, ANB, SOA Table Identity 2582",
                    rates_by_age=_embedded_soa_2012_iam_basic_female_2582(),
                    source="embedded_from_soa_table_2582",
                ),
                "SOA_G2_MALE_2583": RateTable(
                    table_id="SOA_G2_MALE_2583",
                    description="Projection Scale G2 - Male, ANB, SOA Table Identity 2583",
                    rates_by_age=_embedded_soa_g2_male_2583(),
                    source="embedded_from_soa_table_2583",
                ),
            }
        )

    def get(self, table_id: str) -> RateTable:
        try:
            return self._tables[table_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._tables))
            raise KeyError(f"Unknown table_id={table_id!r}. Available: {available}") from exc

    def register(self, table: RateTable) -> None:
        self._tables[table.table_id] = table

    def load_csv(self, table_id: str, path: str | Path, description: str = "") -> RateTable:
        df = pd.read_csv(path)
        required = {"age", "rate"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"CSV table missing required columns: {sorted(missing)}")

        table = RateTable(
            table_id=table_id,
            description=description,
            rates_by_age={int(row.age): float(row.rate) for row in df.itertuples()},
            source=str(path),
        )
        self.register(table)
        return table

    def load_soa_url(
        self,
        table_id: str,
        url: str,
        description: str = "",
        timeout_seconds: int = 30,
    ) -> RateTable:
        """Fetch a SOA table page/XML and parse age-rate pairs.

        Practical note:
        SOA's browser table pages are usually easier to parse consistently than
        the raw XML endpoint. The parser still accepts either source as long as
        age/rate pairs are present in the downloaded text.
        """

        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8", errors="replace")

        rates = _parse_age_rate_pairs_from_text(text)
        if not rates:
            rates = _parse_age_rate_pairs_from_xml(text)

        if not rates:
            raise ValueError(
                f"No age/rate pairs could be parsed from {url!r}. "
                "Use embedded tables or a CSV extract for this run."
            )

        table = RateTable(
            table_id=table_id,
            description=description,
            rates_by_age=rates,
            source=url,
        )
        self.register(table)
        return table


class MortalityDecrementCalculator:
    methodology_version = "mortality_decrements_v0.2.0"

    def __init__(self, assumption_repository: MortalityAssumptionRepository) -> None:
        self.assumption_repository = assumption_repository

    def calculate(self, request: MortalityProjectionRequest) -> MortalityProjectionOutput:
        if request.seriatim.basis is LifeStatus.SINGLE:
            return self._calculate_single_life(request)
        return self._calculate_joint_life(request)

    def _calculate_single_life(
        self, request: MortalityProjectionRequest
    ) -> MortalityProjectionOutput:
        life = request.seriatim.lives[0]
        period_years = request.frequency.years_per_period

        inforce_start = request.seriatim.starting_policy_count
        rows: list[MortalityProjectionRow] = []

        for period in range(1, request.projection_periods + 1):
            period_start, period_end = _period_dates(
                request.seriatim.issue_date, period, request.frequency
            )
            years_from_issue = (period - 1) * period_years
            attained_age = life.issue_age + years_from_issue

            annual = self._adjusted_annual_qx(
                request=request,
                life=life,
                attained_age=attained_age,
                period_start_date=period_start,
            )
            period_qx = _fractional_period_qx(
                annual_qx_provider=lambda age: self._adjusted_annual_qx(
                    request=request,
                    life=life,
                    attained_age=age,
                    period_start_date=period_start,
                ).adjusted_qx,
                attained_age=attained_age,
                period_years=period_years,
                method=request.method,
            )

            mortality_decrement = inforce_start * period_qx

            policy_duration_years = int(np.ceil(years_from_issue))
            lapse_decrement = 0.0
            if request.assumptions.lapse_rate_table is not None:
                annual_lapse_rate = request.assumptions.lapse_rate_table.rate_at_duration(
                    policy_duration_years
                )
                lapse_decrement = inforce_start * annual_lapse_rate

            withdrawal_decrement = 0.0
            if (request.assumptions.withdrawal_assumptions is not None
                    and request.assumptions.withdrawal_assumptions.is_active):
                w_decrement = WithdrawalCalculator.partial_withdrawal_decrement(
                    inforce_start,
                    request.assumptions.withdrawal_assumptions.partial_withdrawal,
                    policy_duration_years,
                )
                withdrawal_decrement = w_decrement

            crediting_accrual = 0.0
            if request.assumptions.creditor_config is not None:
                from actuarial_model.crediting import CreditorCalculator
                crediting_accrual = CreditorCalculator.crediting_accrual(
                    inforce_start,
                    request.assumptions.creditor_config,
                    policy_year=int(years_from_issue) + 1,
                )

            maturity_decrement = 0.0
            inforce_end = max(
                inforce_start
                - mortality_decrement
                - lapse_decrement
                - withdrawal_decrement
                - maturity_decrement
                + crediting_accrual,
                0.0,
            )

            rows.append(
                MortalityProjectionRow(
                    period=period,
                    period_start_date=period_start,
                    period_end_date=period_end,
                    projection_year=years_from_issue,
                    frequency=request.frequency,
                    run_id=request.run_id,
                    policy_id=request.seriatim.policy_id,
                    assumption_set_id=request.assumptions.assumption_set_id,
                    basis=LifeStatus.SINGLE,
                    methodology_version=self.methodology_version,
                    attained_age_1=attained_age,
                    base_annual_qx_1=annual.base_qx,
                    g2_rate_1=annual.g2_rate,
                    adjusted_annual_qx_1=annual.adjusted_qx,
                    period_qx_1=period_qx,
                    single_inforce_start=inforce_start,
                    single_mortality_decrement=mortality_decrement,
                    single_lapse_decrement=lapse_decrement,
                    single_withdrawal_decrement=withdrawal_decrement,
                    single_maturity_decrement=maturity_decrement,
                    single_crediting_accrual=crediting_accrual,
                    single_inforce_end=inforce_end,
                )
            )
            inforce_start = inforce_end

        return self._build_output(request, LifeStatus.SINGLE, rows)

    def _calculate_joint_life(
        self, request: MortalityProjectionRequest
    ) -> MortalityProjectionOutput:
        life1, life2 = request.seriatim.lives
        period_years = request.frequency.years_per_period

        both_alive = request.seriatim.starting_policy_count
        life1_only_alive = 0.0
        life2_only_alive = 0.0
        all_dead = 0.0
        rows: list[MortalityProjectionRow] = []

        for period in range(1, request.projection_periods + 1):
            period_start, period_end = _period_dates(
                request.seriatim.issue_date, period, request.frequency
            )
            years_from_issue = (period - 1) * period_years

            attained_age_1 = life1.issue_age + years_from_issue
            attained_age_2 = life2.issue_age + years_from_issue

            annual1 = self._adjusted_annual_qx(
                request=request,
                life=life1,
                attained_age=attained_age_1,
                period_start_date=period_start,
            )
            annual2 = self._adjusted_annual_qx(
                request=request,
                life=life2,
                attained_age=attained_age_2,
                period_start_date=period_start,
            )

            q1 = _fractional_period_qx(
                annual_qx_provider=lambda age: self._adjusted_annual_qx(
                    request=request,
                    life=life1,
                    attained_age=age,
                    period_start_date=period_start,
                ).adjusted_qx,
                attained_age=attained_age_1,
                period_years=period_years,
                method=request.method,
            )
            q2 = _fractional_period_qx(
                annual_qx_provider=lambda age: self._adjusted_annual_qx(
                    request=request,
                    life=life2,
                    attained_age=age,
                    period_start_date=period_start,
                ).adjusted_qx,
                attained_age=attained_age_2,
                period_years=period_years,
                method=request.method,
            )
            p1 = 1.0 - q1
            p2 = 1.0 - q2

            both_alive_start = both_alive
            life1_only_alive_start = life1_only_alive
            life2_only_alive_start = life2_only_alive
            all_dead_start = all_dead

            both_to_both_alive = both_alive_start * p1 * p2
            both_to_life1_only_alive = both_alive_start * p1 * q2
            both_to_life2_only_alive = both_alive_start * q1 * p2
            both_to_all_dead = both_alive_start * q1 * q2

            life1_only_to_life1_only = life1_only_alive_start * p1
            life1_only_to_all_dead = life1_only_alive_start * q1

            life2_only_to_life2_only = life2_only_alive_start * p2
            life2_only_to_all_dead = life2_only_alive_start * q2

            life1_mortality_decrement = (
                both_alive_start * q1 + life1_only_alive_start * q1
            )
            life2_mortality_decrement = (
                both_alive_start * q2 + life2_only_alive_start * q2
            )
            joint_first_death_decrement = both_alive_start * (1.0 - p1 * p2)
            joint_last_survivor_decrement = (
                both_to_all_dead + life1_only_to_all_dead + life2_only_to_all_dead
            )

            policy_duration_years = int(np.ceil(years_from_issue))
            joint_lapse_decrement = 0.0
            if request.assumptions.lapse_rate_table is not None:
                annual_lapse_rate = request.assumptions.lapse_rate_table.rate_at_duration(
                    policy_duration_years
                )
                joint_lapse_decrement = both_alive_start * annual_lapse_rate

            joint_withdrawal_decrement = 0.0
            if (request.assumptions.withdrawal_assumptions is not None
                    and request.assumptions.withdrawal_assumptions.is_active):
                w_decrement = WithdrawalCalculator.partial_withdrawal_decrement(
                    both_alive_start,
                    request.assumptions.withdrawal_assumptions.partial_withdrawal,
                    policy_duration_years,
                )
                joint_withdrawal_decrement = w_decrement

            joint_crediting_accrual = 0.0
            if request.assumptions.creditor_config is not None:
                from actuarial_model.crediting import CreditorCalculator
                joint_crediting_accrual = CreditorCalculator.crediting_accrual(
                    both_alive_start,
                    request.assumptions.creditor_config,
                    policy_year=int(years_from_issue) + 1,
                )

            joint_maturity_decrement = 0.0

            both_alive = both_to_both_alive + joint_crediting_accrual
            life1_only_alive = both_to_life1_only_alive + life1_only_to_life1_only
            life2_only_alive = both_to_life2_only_alive + life2_only_to_life2_only
            all_dead = (
                all_dead_start
                + both_to_all_dead
                + life1_only_to_all_dead
                + life2_only_to_all_dead
            )

            rows.append(
                MortalityProjectionRow(
                    period=period,
                    period_start_date=period_start,
                    period_end_date=period_end,
                    projection_year=years_from_issue,
                    frequency=request.frequency,
                    run_id=request.run_id,
                    policy_id=request.seriatim.policy_id,
                    assumption_set_id=request.assumptions.assumption_set_id,
                    basis=LifeStatus.JOINT,
                    methodology_version=self.methodology_version,
                    attained_age_1=attained_age_1,
                    base_annual_qx_1=annual1.base_qx,
                    g2_rate_1=annual1.g2_rate,
                    adjusted_annual_qx_1=annual1.adjusted_qx,
                    period_qx_1=q1,
                    attained_age_2=attained_age_2,
                    base_annual_qx_2=annual2.base_qx,
                    g2_rate_2=annual2.g2_rate,
                    adjusted_annual_qx_2=annual2.adjusted_qx,
                    period_qx_2=q2,
                    both_alive_start=both_alive_start,
                    life1_only_alive_start=life1_only_alive_start,
                    life2_only_alive_start=life2_only_alive_start,
                    all_dead_start=all_dead_start,
                    life1_mortality_decrement=life1_mortality_decrement,
                    life2_mortality_decrement=life2_mortality_decrement,
                    joint_first_death_decrement=joint_first_death_decrement,
                    joint_last_survivor_decrement=joint_last_survivor_decrement,
                    joint_lapse_decrement=joint_lapse_decrement,
                    joint_withdrawal_decrement=joint_withdrawal_decrement,
                    joint_maturity_decrement=joint_maturity_decrement,
                    joint_crediting_accrual=joint_crediting_accrual,
                    both_alive_end=both_alive,
                    life1_only_alive_end=life1_only_alive,
                    life2_only_alive_end=life2_only_alive,
                    all_dead_end=all_dead,
                    joint_first_death_inforce_end=both_alive,
                    joint_last_survivor_inforce_end=(
                        both_alive + life1_only_alive + life2_only_alive
                    ),
                )
            )

        return self._build_output(request, LifeStatus.JOINT, rows)

    def _adjusted_annual_qx(
        self,
        *,
        request: MortalityProjectionRequest,
        life: SeriatimLifeInput,
        attained_age: float,
        period_start_date: date,
    ) -> "_AdjustedAnnualQx":
        base_table_id = request.assumptions.base_table_id_by_sex[life.sex]
        g2_table_id = request.assumptions.improvement_table_id_by_sex[life.sex]

        base_table = self.assumption_repository.get(base_table_id)
        g2_table = self.assumption_repository.get(g2_table_id)

        base_qx = base_table.rate_at_age(attained_age)
        g2_rate = g2_table.rate_at_age(attained_age)

        years_since_g2_base = _year_fraction(
            request.assumptions.g2_base_date, period_start_date
        )

        flat_base_date = (
            request.assumptions.flat_improvement_base_date
            or request.seriatim.issue_date
        )
        years_since_flat_base = _year_fraction(flat_base_date, period_start_date)

        g2_factor = (
            1.0 - g2_rate * request.assumptions.g2_scale_multiplier
        ) ** max(years_since_g2_base, 0.0)

        flat_improvement_factor = (
            1.0 - request.assumptions.flat_improvement_rate
        ) ** max(years_since_flat_base, 0.0)

        adjusted_qx = (
            base_qx
            * request.assumptions.mortality_multiplier
            * g2_factor
            * flat_improvement_factor
        )

        return _AdjustedAnnualQx(
            base_qx=float(base_qx),
            g2_rate=float(g2_rate),
            adjusted_qx=float(np.clip(adjusted_qx, 0.0, 1.0)),
        )

    def _build_output(
        self,
        request: MortalityProjectionRequest,
        basis: LifeStatus,
        rows: list[MortalityProjectionRow],
    ) -> MortalityProjectionOutput:
        return MortalityProjectionOutput(
            run_id=request.run_id,
            policy_id=request.seriatim.policy_id,
            assumption_set_id=request.assumptions.assumption_set_id,
            basis=basis,
            frequency=request.frequency,
            projection_periods=request.projection_periods,
            issue_date=request.seriatim.issue_date,
            methodology_version=self.methodology_version,
            records=rows,
        )


class _AdjustedAnnualQx(BaseModel):
    base_qx: float
    g2_rate: float
    adjusted_qx: float


def _period_dates(
    issue_date: date, period: int, frequency: ProjectionFrequency
) -> tuple[date, date]:
    months_per_period = frequency.months_per_period
    start = pd.Timestamp(issue_date) + pd.DateOffset(
        months=(period - 1) * months_per_period
    )
    end = start + pd.DateOffset(months=months_per_period)
    return start.date(), end.date()


def _year_fraction(start: date, end: date) -> float:
    return (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25


def _fractional_period_qx(
    *,
    annual_qx_provider,
    attained_age: float,
    period_years: float,
    method: MortalityMethod,
) -> float:
    """Convert annual qx into period qx, splitting at integer ages."""

    if period_years <= 0.0:
        raise ValueError("period_years must be positive.")

    survival_probability = 1.0
    age_cursor = attained_age
    remaining_years = period_years

    while remaining_years > 1e-12:
        floor_age = np.floor(age_cursor)
        years_until_next_integer_age = (floor_age + 1.0) - age_cursor

        if years_until_next_integer_age <= 1e-12:
            years_until_next_integer_age = 1.0

        step_years = min(remaining_years, years_until_next_integer_age)
        annual_qx = float(np.clip(annual_qx_provider(age_cursor), 0.0, 1.0))

        if method is MortalityMethod.CONSTANT_FORCE:
            step_qx = 1.0 - (1.0 - annual_qx) ** step_years
        elif method is MortalityMethod.UDD:
            elapsed_in_age_year = age_cursor - np.floor(age_cursor)
            denominator = 1.0 - elapsed_in_age_year * annual_qx
            step_qx = 1.0 if denominator <= 0.0 else step_years * annual_qx / denominator
        else:
            raise ValueError(f"Unsupported mortality method: {method}")

        step_qx = float(np.clip(step_qx, 0.0, 1.0))
        survival_probability *= 1.0 - step_qx
        age_cursor += step_years
        remaining_years -= step_years

    return float(np.clip(1.0 - survival_probability, 0.0, 1.0))


def _parse_age_rate_pairs_from_text(text: str) -> dict[int, float]:
    """Parse age/rate pairs from SOA ViewTable-style text or simple text."""

    # Strip simple HTML tags so "60 0.005662" style rows remain parseable.
    text_no_tags = re.sub(r"<[^>]+>", "\n", text)
    rates: dict[int, float] = {}

    for line in text_no_tags.splitlines():
        clean = " ".join(line.strip().split())
        match = re.fullmatch(r"(\d{1,3})\s+([0-9]*\.?[0-9]+(?:[Ee][+-]?\d+)?)", clean)
        if match:
            age = int(match.group(1))
            rate = float(match.group(2))
            if 0 <= age <= 130 and 0 <= rate <= 1:
                rates[age] = rate

    return dict(sorted(rates.items()))


def _parse_age_rate_pairs_from_xml(text: str) -> dict[int, float]:
    """Best-effort parser for XML sources with numeric age/rate fields.

    This is intentionally conservative. If a raw XTbML source has a structure
    that does not expose age/rate pairs clearly, use a CSV extract or embedded
    table instead of silently misreading it.
    """

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}

    # First pass: collect explicit attributes such as age/rate or row/value.
    rates: dict[int, float] = {}
    for elem in root.iter():
        attrs = {k.lower(): v for k, v in elem.attrib.items()}
        age_raw = attrs.get("age") or attrs.get("row") or attrs.get("x")
        rate_raw = attrs.get("rate") or attrs.get("value") or attrs.get("qx")
        if age_raw is not None and rate_raw is not None:
            try:
                age = int(float(age_raw))
                rate = float(rate_raw)
            except ValueError:
                continue
            if 0 <= age <= 130 and 0 <= rate <= 1:
                rates[age] = rate

    return dict(sorted(rates.items()))


def _table_from_multiline_pairs(pairs: str) -> dict[int, float]:
    rates: dict[int, float] = {}
    for line in pairs.strip().splitlines():
        age_raw, rate_raw = line.split()
        rates[int(age_raw)] = float(rate_raw)
    return rates


def _embedded_soa_2012_iam_basic_male_2581() -> dict[int, float]:
    return _table_from_multiline_pairs(
        """
        0 0.001783
        1 0.000446
        2 0.000306
        3 0.000254
        4 0.000193
        5 0.000186
        6 0.000184
        7 0.000177
        8 0.000159
        9 0.000143
        10 0.000126
        11 0.000123
        12 0.000147
        13 0.000188
        14 0.000236
        15 0.000282
        16 0.000325
        17 0.000364
        18 0.000399
        19 0.00043
        20 0.000459
        21 0.000492
        22 0.000526
        23 0.000569
        24 0.000616
        25 0.000669
        26 0.000728
        27 0.000764
        28 0.000789
        29 0.000808
        30 0.000824
        31 0.000834
        32 0.000838
        33 0.000828
        34 0.000808
        35 0.000789
        36 0.000783
        37 0.0008
        38 0.000837
        39 0.000889
        40 0.000955
        41 0.001029
        42 0.00111
        43 0.001188
        44 0.001268
        45 0.001355
        46 0.001464
        47 0.001615
        48 0.001808
        49 0.002032
        50 0.002285
        51 0.002557
        52 0.002828
        53 0.003088
        54 0.003345
        55 0.003616
        56 0.003922
        57 0.004272
        58 0.004681
        59 0.005146
        60 0.005662
        61 0.006237
        62 0.006854
        63 0.00751
        64 0.00822
        65 0.009007
        66 0.009497
        67 0.010085
        68 0.010787
        69 0.011625
        70 0.012619
        71 0.013798
        72 0.015195
        73 0.016834
        74 0.018733
        75 0.020905
        76 0.023367
        77 0.026155
        78 0.029306
        79 0.032858
        80 0.036927
        81 0.041703
        82 0.046957
        83 0.052713
        84 0.059148
        85 0.066505
        86 0.075015
        87 0.084823
        88 0.095987
        89 0.108482
        90 0.122214
        91 0.136799
        92 0.152409
        93 0.169078
        94 0.186882
        95 0.205844
        96 0.219247
        97 0.238612
        98 0.258341
        99 0.278219
        100 0.298452
        101 0.32361
        102 0.344191
        103 0.364633
        104 0.384783
        105 0.4
        106 0.4
        107 0.4
        108 0.4
        109 0.4
        110 0.4
        111 0.4
        112 0.4
        113 0.4
        114 0.4
        115 0.4
        116 0.4
        117 0.4
        118 0.4
        119 0.4
        120 0.4
        """
    )


def _embedded_soa_2012_iam_basic_female_2582() -> dict[int, float]:
    return _table_from_multiline_pairs(
        """
        0 0.001801
        1 0.00045
        2 0.000287
        3 0.000199
        4 0.000152
        5 0.000139
        6 0.00013
        7 0.000122
        8 0.000105
        9 9.8E-05
        10 9.4E-05
        11 9.6E-05
        12 0.000105
        13 0.00012
        14 0.000146
        15 0.000174
        16 0.000199
        17 0.00022
        18 0.000234
        19 0.000245
        20 0.000253
        21 0.00026
        22 0.000266
        23 0.000272
        24 0.000275
        25 0.000277
        26 0.000284
        27 0.00029
        28 0.0003
        29 0.000313
        30 0.000333
        31 0.000357
        32 0.000375
        33 0.00039
        34 0.000405
        35 0.000424
        36 0.000447
        37 0.000476
        38 0.000514
        39 0.00056
        40 0.000613
        41 0.000667
        42 0.000723
        43 0.000774
        44 0.000823
        45 0.000866
        46 0.000917
        47 0.000983
        48 0.001072
        49 0.001168
        50 0.00129
        51 0.001453
        52 0.001622
        53 0.001792
        54 0.001972
        55 0.002166
        56 0.002393
        57 0.002666
        58 0.003
        59 0.003393
        60 0.003844
        61 0.004352
        62 0.004899
        63 0.005482
        64 0.006118
        65 0.006829
        66 0.007279
        67 0.007821
        68 0.008475
        69 0.009234
        70 0.010083
        71 0.011011
        72 0.01203
        73 0.013154
        74 0.014415
        75 0.015869
        76 0.017555
        77 0.0195
        78 0.021758
        79 0.024412
        80 0.027579
        81 0.031501
        82 0.036122
        83 0.041477
        84 0.047589
        85 0.054441
        86 0.061972
        87 0.070155
        88 0.078963
        89 0.088336
        90 0.098197
        91 0.108323
        92 0.119188
        93 0.131334
        94 0.145521
        95 0.162722
        96 0.18212
        97 0.199661
        98 0.217946
        99 0.236834
        100 0.256357
        101 0.283802
        102 0.304716
        103 0.325819
        104 0.346936
        105 0.367898
        106 0.387607
        107 0.4
        108 0.4
        109 0.4
        110 0.4
        111 0.4
        112 0.4
        113 0.4
        114 0.4
        115 0.4
        116 0.4
        117 0.4
        118 0.4
        119 0.4
        120 0.4
        """
    )


def _embedded_soa_g2_male_2583() -> dict[int, float]:
    return _table_from_multiline_pairs(
        """
        0 0.01
        1 0.01
        2 0.01
        3 0.01
        4 0.01
        5 0.01
        6 0.01
        7 0.01
        8 0.01
        9 0.01
        10 0.01
        11 0.01
        12 0.01
        13 0.01
        14 0.01
        15 0.01
        16 0.01
        17 0.01
        18 0.01
        19 0.01
        20 0.01
        21 0.01
        22 0.01
        23 0.01
        24 0.01
        25 0.01
        26 0.01
        27 0.01
        28 0.01
        29 0.01
        30 0.01
        31 0.01
        32 0.01
        33 0.01
        34 0.01
        35 0.01
        36 0.01
        37 0.01
        38 0.01
        39 0.01
        40 0.01
        41 0.01
        42 0.01
        43 0.01
        44 0.01
        45 0.01
        46 0.01
        47 0.01
        48 0.01
        49 0.01
        50 0.01
        51 0.011
        52 0.011
        53 0.012
        54 0.012
        55 0.013
        56 0.013
        57 0.014
        58 0.014
        59 0.015
        60 0.015
        61 0.015
        62 0.015
        63 0.015
        64 0.015
        65 0.015
        66 0.015
        67 0.015
        68 0.015
        69 0.015
        70 0.015
        71 0.015
        72 0.015
        73 0.015
        74 0.015
        75 0.015
        76 0.015
        77 0.015
        78 0.015
        79 0.015
        80 0.015
        81 0.014
        82 0.013
        83 0.013
        84 0.012
        85 0.011
        86 0.010
        87 0.009
        88 0.009
        89 0.008
        90 0.007
        91 0.007
        92 0.006
        93 0.005
        94 0.005
        95 0.004
        96 0.004
        97 0.003
        98 0.003
        99 0.002
        100 0.002
        101 0.002
        102 0.001
        103 0.001
        104 0.000
        105 0.000
        """
    )

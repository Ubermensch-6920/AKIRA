"""Withdrawal, surrender charge, and MVA rate tables for MYGA products."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SurrenderChargeSchedule(BaseModel):
    """Declining surrender charge schedule indexed by policy year."""

    schedule_id: str
    product_code: str
    charges_by_year: dict[int, float]
    description: str = ""

    @field_validator("charges_by_year")
    @classmethod
    def validate_charges(cls, v: dict[int, float]) -> dict[int, float]:
        for year, charge in v.items():
            if year <= 0:
                raise ValueError("Policy years must be positive")
            if not 0 <= charge <= 1:
                raise ValueError(f"Surrender charge at year {year} must be between 0 and 1")
        return v

    def charge_at_year(self, policy_year: int) -> float:
        """Return surrender charge rate for given policy year (0.0 if beyond schedule)."""
        return self.charges_by_year.get(policy_year, 0.0)

    @property
    def charge_period_years(self) -> int:
        """Number of years the surrender charge schedule runs."""
        return max(self.charges_by_year) if self.charges_by_year else 0


class FreeWithdrawalConfig(BaseModel):
    """Annual free withdrawal allowance — no surrender charge or MVA applied.

    ``basis`` follows the product documents: Athene MYG (doc 76009) frees
    ``annual_free_pct`` (10%) of accumulated value each contract year;
    Athene MaxRate (doc 76047) frees the interest earned — the fixed
    strategy rate times the anniversary accumulated value — in which case
    ``annual_free_pct`` is ignored and the credited rate is supplied by
    the caller.
    """

    basis: Literal["PCT_AV", "INTEREST_EARNED"] = "PCT_AV"
    annual_free_pct: float = 0.10
    applies_from_year: int = 1

    @field_validator("annual_free_pct")
    @classmethod
    def validate_pct(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("annual_free_pct must be between 0 and 1")
        return v


class MvaConfig(BaseModel):
    """
    Market Value Adjustment applied to the excess-withdrawal portion
    of any withdrawal or surrender beyond the free-withdrawal amount.

    Simple configurable formula:
        mva_rate = -(rate_change_bps / 10_000) * duration_sensitivity

    Where rate_change_bps is positive when market rates have risen since
    issue (MVA hurts policyholder) and negative when rates have fallen
    (MVA helps policyholder). The resulting rate is clamped to [floor, ceiling].

    Replace this formula by overriding duration_sensitivity or swapping in a
    richer model when a full interest-rate path is available.
    """

    is_active: bool = True
    duration_sensitivity: float = 1.0
    floor: float = -0.10
    ceiling: float = 0.10

    @field_validator("floor", "ceiling")
    @classmethod
    def validate_bounds(cls, v: float) -> float:
        if not -1 <= v <= 1:
            raise ValueError("MVA floor/ceiling must be between -1 and 1")
        return v

    def adjustment_rate(self, rate_change_bps: float) -> float:
        """
        Compute the MVA rate given interest rate movement since issue.

        Args:
            rate_change_bps: Change in reference rate in basis points.
                             Positive = rates rose, Negative = rates fell.

        Returns:
            MVA rate to apply to excess withdrawal amount.
            Negative rate reduces proceeds; positive rate increases proceeds.
        """
        raw = -(rate_change_bps / 10_000) * self.duration_sensitivity
        return max(self.floor, min(self.ceiling, raw))


class PartialWithdrawalTable(BaseModel):
    """
    Annual partial withdrawal rates by policy duration.

    Rates represent the fraction of in-force policies expected to take
    a partial withdrawal in a given year, independent of full lapses.
    """

    table_id: str
    base_annual_rate: float = 0.05
    rates_by_duration: dict[int, float] = Field(default_factory=dict)
    description: str = ""

    @field_validator("base_annual_rate")
    @classmethod
    def validate_base(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("base_annual_rate must be between 0 and 1")
        return v

    @field_validator("rates_by_duration")
    @classmethod
    def validate_rates(cls, v: dict[int, float]) -> dict[int, float]:
        for dur, rate in v.items():
            if dur <= 0:
                raise ValueError("Duration years must be positive")
            if not 0 <= rate <= 1:
                raise ValueError(f"Withdrawal rate at duration {dur} must be between 0 and 1")
        return v

    def rate_at_duration(self, duration_years: int) -> float:
        """Get partial withdrawal rate for the given policy duration."""
        return self.rates_by_duration.get(duration_years, self.base_annual_rate)


class SurrenderChargeRepository:
    """Registry of surrender charge schedules.

    Pre-populated with standard Athene MYG and MaxRate schedules sourced
    from product documents (76009 and 76047). Additional schedules can be
    registered at runtime.
    """

    def __init__(self) -> None:
        self._schedules: dict[str, SurrenderChargeSchedule] = {}

    @staticmethod
    def with_athene_schedules() -> "SurrenderChargeRepository":
        """Factory: pre-populate with Athene MYG + MaxRate standard schedules."""
        repo = SurrenderChargeRepository()

        # ── Athene MYG (with MVA) schedules — product doc 76009 ─────────────
        repo.register(SurrenderChargeSchedule(
            schedule_id="ATHENE_MYG_3",
            product_code="MYG3",
            charges_by_year={1: 0.08, 2: 0.08, 3: 0.07},
            description="Athene MYG 3-year surrender charges (doc 76009)",
        ))
        repo.register(SurrenderChargeSchedule(
            schedule_id="ATHENE_MYG_5",
            product_code="MYG5",
            charges_by_year={1: 0.08, 2: 0.07, 3: 0.06, 4: 0.05, 5: 0.04},
            description="Athene MYG 5-year surrender charges (doc 76009)",
        ))
        repo.register(SurrenderChargeSchedule(
            schedule_id="ATHENE_MYG_7",
            product_code="MYG7",
            charges_by_year={1: 0.08, 2: 0.08, 3: 0.07, 4: 0.06, 5: 0.05, 6: 0.04, 7: 0.03},
            description="Athene MYG 7-year surrender charges (doc 76009)",
        ))

        # ── Athene MYG CA-specific schedules — product doc 76009 ─────────────
        repo.register(SurrenderChargeSchedule(
            schedule_id="ATHENE_MYG_3_CA",
            product_code="MYG3_CA",
            charges_by_year={1: 0.08, 2: 0.073, 3: 0.063},
            description="Athene MYG 3-year CA surrender charges (doc 76009)",
        ))
        repo.register(SurrenderChargeSchedule(
            schedule_id="ATHENE_MYG_7_CA",
            product_code="MYG7_CA",
            charges_by_year={
                1: 0.08, 2: 0.073, 3: 0.063,
                4: 0.053, 5: 0.042, 6: 0.032, 7: 0.021,
            },
            description="Athene MYG 7-year CA surrender charges (doc 76009)",
        ))

        # ── Athene MaxRate NY schedules — product doc 76047 ──────────────────
        repo.register(SurrenderChargeSchedule(
            schedule_id="ATHENE_MAXRATE_3",
            product_code="MAXRATE3",
            charges_by_year={1: 0.10, 2: 0.10, 3: 0.10},
            description="Athene MaxRate 3-year surrender charges (doc 76047)",
        ))
        repo.register(SurrenderChargeSchedule(
            schedule_id="ATHENE_MAXRATE_5",
            product_code="MAXRATE5",
            charges_by_year={1: 0.10, 2: 0.10, 3: 0.10, 4: 0.10, 5: 0.10},
            description="Athene MaxRate 5-year surrender charges (doc 76047)",
        ))
        repo.register(SurrenderChargeSchedule(
            schedule_id="ATHENE_MAXRATE_7",
            product_code="MAXRATE7",
            charges_by_year={
                1: 0.10, 2: 0.10, 3: 0.10,
                4: 0.10, 5: 0.10, 6: 0.10, 7: 0.10,
            },
            description="Athene MaxRate 7-year surrender charges (doc 76047)",
        ))

        return repo

    def register(self, schedule: SurrenderChargeSchedule) -> None:
        self._schedules[schedule.schedule_id] = schedule

    def get(self, schedule_id: str) -> SurrenderChargeSchedule:
        if schedule_id not in self._schedules:
            raise ValueError(f"Surrender schedule '{schedule_id}' not found in registry")
        return self._schedules[schedule_id]

    def list_schedules(self) -> list[str]:
        return list(self._schedules.keys())

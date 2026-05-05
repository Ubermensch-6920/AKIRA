"""Lapse rate tables and assumption repositories."""

from pydantic import BaseModel, Field, field_validator


class LapseRateTable(BaseModel):
    """Uniform lapse rate table with optional shock periods."""

    table_id: str
    base_annual_rate: float
    shock_rates: dict[int, float] = Field(default_factory=dict)
    description: str = ""
    source: str = "AKIRA"

    @field_validator("base_annual_rate")
    @classmethod
    def validate_base_rate(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("base_annual_rate must be between 0 and 1")
        return v

    @field_validator("shock_rates")
    @classmethod
    def validate_shock_rates(cls, v: dict[int, float]) -> dict[int, float]:
        for year, rate in v.items():
            if not 0 <= rate <= 1:
                raise ValueError(f"shock rate at year {year} must be between 0 and 1")
            if year <= 0:
                raise ValueError("policy duration years must be positive")
        return v

    def rate_at_duration(self, policy_duration_years: int) -> float:
        """Get lapse rate for given policy duration (in years)."""
        return self.shock_rates.get(policy_duration_years, self.base_annual_rate)


class LapseAssumptionRepository:
    """Manages lapse rate table registry."""

    def __init__(self) -> None:
        self._tables: dict[str, LapseRateTable] = {}

    @staticmethod
    def default() -> "LapseAssumptionRepository":
        """Factory: creates default assumption repository with standard tables."""
        repo = LapseAssumptionRepository()
        repo.register(
            LapseRateTable(
                table_id="standard_1pct_no_shock",
                base_annual_rate=0.01,
                description="Standard 1% base lapse rate",
            )
        )
        repo.register(
            LapseRateTable(
                table_id="standard_1pct_shocks",
                base_annual_rate=0.01,
                shock_rates={3: 0.20, 5: 0.40, 7: 0.50},
                description="1% base with shocks at years 3, 5, 7",
            )
        )
        return repo

    def register(self, table: LapseRateTable) -> None:
        """Register a lapse rate table."""
        self._tables[table.table_id] = table

    def get(self, table_id: str) -> LapseRateTable:
        """Retrieve a registered table by ID."""
        if table_id not in self._tables:
            raise ValueError(f"Lapse table '{table_id}' not found in registry")
        return self._tables[table_id]

    def list_tables(self) -> list[str]:
        """List all registered table IDs."""
        return list(self._tables.keys())

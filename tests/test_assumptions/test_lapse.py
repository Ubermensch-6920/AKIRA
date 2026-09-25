"""Tests for lapse rate tables."""

import pytest

from actuarial_model.assumptions.lapse import LapseAssumptionRepository, LapseRateTable


class TestLapseRateTable:
    """Test LapseRateTable functionality."""

    def test_uniform_rate(self):
        """Test that uniform base rate is returned for all durations."""
        table = LapseRateTable(
            table_id="test_uniform",
            base_annual_rate=0.01,
        )
        assert table.rate_at_duration(1) == 0.01
        assert table.rate_at_duration(5) == 0.01
        assert table.rate_at_duration(10) == 0.01

    def test_shock_rates(self):
        """Test that shock rates override base rate at specific durations."""
        table = LapseRateTable(
            table_id="test_shocks",
            base_annual_rate=0.01,
            shock_rates={3: 0.20, 5: 0.40, 7: 0.50},
        )
        assert table.rate_at_duration(1) == 0.01
        assert table.rate_at_duration(2) == 0.01
        assert table.rate_at_duration(3) == 0.20
        assert table.rate_at_duration(4) == 0.01
        assert table.rate_at_duration(5) == 0.40
        assert table.rate_at_duration(6) == 0.01
        assert table.rate_at_duration(7) == 0.50
        assert table.rate_at_duration(8) == 0.01

    def test_validate_base_rate_bounds(self):
        """Test validation of base rate bounds."""
        with pytest.raises(ValueError):
            LapseRateTable(
                table_id="invalid_low",
                base_annual_rate=-0.01,
            )

        with pytest.raises(ValueError):
            LapseRateTable(
                table_id="invalid_high",
                base_annual_rate=1.01,
            )

    def test_validate_shock_rate_bounds(self):
        """Test validation of shock rate bounds."""
        with pytest.raises(ValueError):
            LapseRateTable(
                table_id="invalid_shock_low",
                base_annual_rate=0.01,
                shock_rates={3: -0.01},
            )

        with pytest.raises(ValueError):
            LapseRateTable(
                table_id="invalid_shock_high",
                base_annual_rate=0.01,
                shock_rates={3: 1.01},
            )

    def test_validate_shock_duration_positive(self):
        """Test validation that shock durations are positive."""
        with pytest.raises(ValueError):
            LapseRateTable(
                table_id="invalid_duration",
                base_annual_rate=0.01,
                shock_rates={0: 0.20},
            )

        with pytest.raises(ValueError):
            LapseRateTable(
                table_id="invalid_duration",
                base_annual_rate=0.01,
                shock_rates={-1: 0.20},
            )


class TestLapseAssumptionRepository:
    """Test LapseAssumptionRepository functionality."""

    def test_default_repository(self):
        """Test that default repository contains standard tables."""
        repo = LapseAssumptionRepository.default()
        tables = repo.list_tables()
        assert "standard_1pct_no_shock" in tables
        assert "standard_1pct_shocks" in tables

    def test_register_and_get(self):
        """Test registering and retrieving tables."""
        repo = LapseAssumptionRepository()
        table = LapseRateTable(
            table_id="custom_table",
            base_annual_rate=0.02,
        )
        repo.register(table)
        retrieved = repo.get("custom_table")
        assert retrieved.base_annual_rate == 0.02

    def test_get_nonexistent_table(self):
        """Test that getting nonexistent table raises error."""
        repo = LapseAssumptionRepository()
        with pytest.raises(ValueError):
            repo.get("nonexistent")

    def test_default_table_with_shocks(self):
        """Test default table with user-specified shocks."""
        repo = LapseAssumptionRepository.default()
        table = repo.get("standard_1pct_shocks")
        assert table.base_annual_rate == 0.01
        assert table.shock_rates == {3: 0.20, 5: 0.40, 7: 0.50}

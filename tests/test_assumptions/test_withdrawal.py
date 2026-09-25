"""Tests for withdrawal rates, surrender charges, and MVA config."""

import pytest

from actuarial_model.assumptions.withdrawal import (
    FreeWithdrawalConfig,
    MvaConfig,
    PartialWithdrawalTable,
    SurrenderChargeRepository,
    SurrenderChargeSchedule,
)

# ── SurrenderChargeSchedule ───────────────────────────────────────────────────

class TestSurrenderChargeSchedule:
    def test_charge_within_period(self):
        schedule = SurrenderChargeSchedule(
            schedule_id="TEST",
            product_code="MYG5",
            charges_by_year={1: 0.08, 2: 0.07, 3: 0.06, 4: 0.05, 5: 0.04},
        )
        assert schedule.charge_at_year(1) == 0.08
        assert schedule.charge_at_year(3) == 0.06
        assert schedule.charge_at_year(5) == 0.04

    def test_charge_beyond_period_is_zero(self):
        schedule = SurrenderChargeSchedule(
            schedule_id="TEST",
            product_code="MYG3",
            charges_by_year={1: 0.08, 2: 0.08, 3: 0.07},
        )
        assert schedule.charge_at_year(4) == 0.0
        assert schedule.charge_at_year(10) == 0.0

    def test_charge_period_years(self):
        schedule = SurrenderChargeSchedule(
            schedule_id="TEST",
            product_code="MYG7",
            charges_by_year={1: 0.08, 2: 0.08, 3: 0.07, 4: 0.06, 5: 0.05, 6: 0.04, 7: 0.03},
        )
        assert schedule.charge_period_years == 7

    def test_validate_charge_bounds(self):
        with pytest.raises(ValueError):
            SurrenderChargeSchedule(
                schedule_id="BAD", product_code="X",
                charges_by_year={1: 1.05},
            )

    def test_validate_year_positive(self):
        with pytest.raises(ValueError):
            SurrenderChargeSchedule(
                schedule_id="BAD", product_code="X",
                charges_by_year={0: 0.08},
            )


# ── Athene standard schedules ─────────────────────────────────────────────────

class TestSurrenderChargeRepository:
    def setup_method(self):
        self.repo = SurrenderChargeRepository.with_athene_schedules()

    def test_all_athene_schedules_present(self):
        ids = self.repo.list_schedules()
        for expected in [
            "ATHENE_MYG_3", "ATHENE_MYG_5", "ATHENE_MYG_7",
            "ATHENE_MYG_3_CA", "ATHENE_MYG_7_CA",
            "ATHENE_MAXRATE_3", "ATHENE_MAXRATE_5", "ATHENE_MAXRATE_7",
        ]:
            assert expected in ids

    def test_myg_3_schedule(self):
        """Athene MYG 3: 8%, 8%, 7% (doc 76009)."""
        s = self.repo.get("ATHENE_MYG_3")
        assert s.charge_at_year(1) == 0.08
        assert s.charge_at_year(2) == 0.08
        assert s.charge_at_year(3) == 0.07
        assert s.charge_at_year(4) == 0.0

    def test_myg_5_schedule(self):
        """Athene MYG 5: 8%, 7%, 6%, 5%, 4% (doc 76009)."""
        s = self.repo.get("ATHENE_MYG_5")
        assert s.charge_at_year(1) == 0.08
        assert s.charge_at_year(2) == 0.07
        assert s.charge_at_year(5) == 0.04
        assert s.charge_at_year(6) == 0.0

    def test_myg_7_schedule(self):
        """Athene MYG 7: 8%, 8%, 7%, 6%, 5%, 4%, 3% (doc 76009)."""
        s = self.repo.get("ATHENE_MYG_7")
        assert s.charge_at_year(1) == 0.08
        assert s.charge_at_year(7) == 0.03
        assert s.charge_at_year(8) == 0.0

    def test_myg_3_ca_schedule(self):
        """Athene MYG 3 CA: 8%, 7.3%, 6.3% (doc 76009)."""
        s = self.repo.get("ATHENE_MYG_3_CA")
        assert s.charge_at_year(1) == 0.08
        assert s.charge_at_year(2) == pytest.approx(0.073)
        assert s.charge_at_year(3) == pytest.approx(0.063)

    def test_maxrate_7_schedule(self):
        """Athene MaxRate 7: flat 10% all 7 years (doc 76047)."""
        s = self.repo.get("ATHENE_MAXRATE_7")
        for yr in range(1, 8):
            assert s.charge_at_year(yr) == 0.10
        assert s.charge_at_year(8) == 0.0

    def test_get_nonexistent_raises(self):
        with pytest.raises(ValueError):
            self.repo.get("NONEXISTENT")

    def test_custom_register(self):
        self.repo.register(SurrenderChargeSchedule(
            schedule_id="CUSTOM",
            product_code="CUSTOM_PROD",
            charges_by_year={1: 0.05, 2: 0.03},
        ))
        s = self.repo.get("CUSTOM")
        assert s.charge_at_year(1) == 0.05


# ── FreeWithdrawalConfig ──────────────────────────────────────────────────────

class TestFreeWithdrawalConfig:
    def test_default_10_pct(self):
        cfg = FreeWithdrawalConfig()
        assert cfg.annual_free_pct == 0.10
        assert cfg.applies_from_year == 1

    def test_validate_pct_bounds(self):
        with pytest.raises(ValueError):
            FreeWithdrawalConfig(annual_free_pct=1.1)
        with pytest.raises(ValueError):
            FreeWithdrawalConfig(annual_free_pct=-0.01)


# ── MvaConfig ─────────────────────────────────────────────────────────────────

class TestMvaConfig:
    def test_positive_rate_change_reduces_proceeds(self):
        """Rates rose 100bps: MVA should be negative (hurts policyholder)."""
        cfg = MvaConfig(duration_sensitivity=1.0)
        rate = cfg.adjustment_rate(rate_change_bps=100)
        assert rate < 0

    def test_negative_rate_change_increases_proceeds(self):
        """Rates fell 100bps: MVA should be positive (helps policyholder)."""
        cfg = MvaConfig(duration_sensitivity=1.0)
        rate = cfg.adjustment_rate(rate_change_bps=-100)
        assert rate > 0

    def test_floor_clamp(self):
        """Extreme rate rise should be clamped to floor."""
        cfg = MvaConfig(duration_sensitivity=1.0, floor=-0.10)
        rate = cfg.adjustment_rate(rate_change_bps=5000)
        assert rate == pytest.approx(-0.10)

    def test_ceiling_clamp(self):
        """Extreme rate fall should be clamped to ceiling."""
        cfg = MvaConfig(duration_sensitivity=1.0, ceiling=0.10)
        rate = cfg.adjustment_rate(rate_change_bps=-5000)
        assert rate == pytest.approx(0.10)

    def test_zero_rate_change(self):
        cfg = MvaConfig()
        assert cfg.adjustment_rate(0) == 0.0

    def test_inactive_mva_always_zero(self):
        cfg = MvaConfig(is_active=False)
        assert cfg.adjustment_rate(300) == pytest.approx(-0.03)

    def test_higher_duration_sensitivity(self):
        cfg = MvaConfig(duration_sensitivity=5.0)
        rate = cfg.adjustment_rate(rate_change_bps=100)
        assert rate == pytest.approx(-0.05)


# ── PartialWithdrawalTable ────────────────────────────────────────────────────

class TestPartialWithdrawalTable:
    def test_base_rate_fallback(self):
        table = PartialWithdrawalTable(table_id="T", base_annual_rate=0.05)
        assert table.rate_at_duration(1) == 0.05
        assert table.rate_at_duration(99) == 0.05

    def test_duration_override(self):
        table = PartialWithdrawalTable(
            table_id="T",
            base_annual_rate=0.05,
            rates_by_duration={3: 0.12, 5: 0.18},
        )
        assert table.rate_at_duration(1) == 0.05
        assert table.rate_at_duration(3) == 0.12
        assert table.rate_at_duration(5) == 0.18
        assert table.rate_at_duration(6) == 0.05

    def test_validate_rate_bounds(self):
        with pytest.raises(ValueError):
            PartialWithdrawalTable(table_id="T", base_annual_rate=1.5)

    def test_validate_duration_positive(self):
        with pytest.raises(ValueError):
            PartialWithdrawalTable(
                table_id="T", base_annual_rate=0.05,
                rates_by_duration={0: 0.10},
            )




# ── WithdrawalAssumptions integration ────────────────────────────────────────

class TestWithdrawalAssumptionsInAssumptionSet:
    def test_withdrawal_wired_into_all_frameworks(self):
        from datetime import date

        from actuarial_model.assumptions import AssumptionSet, Framework

        a = AssumptionSet(
            assumption_set_id="test",
            version="0.1.0",
            description="test",
            created_by="pytest",
            created_date=date(2025, 1, 1),
        )
        for framework in [f for f in Framework if f is not Framework.NAIC_RBC]:
            fw = a.framework_config(framework)
            assert hasattr(fw, "withdrawal"), f"{framework.value} missing withdrawal"
            assert fw.withdrawal.is_active is True

    def test_set_product_specific_schedule(self):
        from datetime import date

        from actuarial_model.assumptions import AssumptionSet, WithdrawalAssumptions

        a = AssumptionSet(
            assumption_set_id="test",
            version="0.1.0",
            description="test",
            created_by="pytest",
            created_date=date(2025, 1, 1),
        )
        a.ebs.bel.withdrawal = WithdrawalAssumptions(
            surrender_schedule_id="ATHENE_MYG_7",
            free_withdrawal=FreeWithdrawalConfig(annual_free_pct=0.10),
        )
        assert a.ebs.bel.withdrawal.surrender_schedule_id == "ATHENE_MYG_7"
        assert a.ebs.bel.withdrawal.free_withdrawal.annual_free_pct == 0.10

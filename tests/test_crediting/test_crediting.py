"""Tests for interest crediting rates and calculations."""

import pytest

from actuarial_model.assumptions.sets import CreditorConfig, FixedCreditingConfig
from actuarial_model.crediting import CreditorCalculator
from actuarial_model.mortality.decrements import ProjectionFrequency


class TestFixedCreditingConfig:
    def test_default_rate(self):
        cfg = FixedCreditingConfig()
        assert cfg.annual_rate == 0.03

    def test_custom_rate(self):
        cfg = FixedCreditingConfig(annual_rate=0.05)
        assert cfg.annual_rate == 0.05


class TestCreditorConfig:
    def test_default_fixed_strategy(self):
        cfg = CreditorConfig()
        assert cfg.strategy == "fixed"
        assert cfg.fixed.annual_rate == 0.03
        assert cfg.is_active is True

    def test_inactive_creditor(self):
        cfg = CreditorConfig(is_active=False)
        assert cfg.is_active is False

    def test_custom_fixed_rate(self):
        cfg = CreditorConfig(fixed=FixedCreditingConfig(annual_rate=0.04))
        assert cfg.fixed.annual_rate == 0.04


class TestCreditorCalculator:
    def test_fixed_crediting_rate(self):
        config = CreditorConfig(fixed=FixedCreditingConfig(annual_rate=0.03))
        rate = CreditorCalculator.get_annual_crediting_rate(config)
        assert rate == pytest.approx(0.03)

    def test_crediting_rate_by_policy_year(self):
        config = CreditorConfig(fixed=FixedCreditingConfig(annual_rate=0.03))
        rate1 = CreditorCalculator.get_annual_crediting_rate(config, policy_year=1)
        rate5 = CreditorCalculator.get_annual_crediting_rate(config, policy_year=5)
        assert rate1 == pytest.approx(0.03)
        assert rate5 == pytest.approx(0.03)

    def test_crediting_accrual(self):
        config = CreditorConfig(fixed=FixedCreditingConfig(annual_rate=0.03))
        accrual = CreditorCalculator.crediting_accrual(100_000, config)
        assert accrual == pytest.approx(3_000)

    def test_crediting_accrual_zero_inforce(self):
        config = CreditorConfig(fixed=FixedCreditingConfig(annual_rate=0.03))
        accrual = CreditorCalculator.crediting_accrual(0.0, config)
        assert accrual == pytest.approx(0.0)

    def test_inactive_crediting_zero(self):
        config = CreditorConfig(is_active=False)
        accrual = CreditorCalculator.crediting_accrual(100_000, config)
        assert accrual == pytest.approx(0.0)

    def test_high_crediting_rate(self):
        config = CreditorConfig(fixed=FixedCreditingConfig(annual_rate=0.10))
        accrual = CreditorCalculator.crediting_accrual(100_000, config)
        assert accrual == pytest.approx(10_000)

    def test_annual_to_monthly_conversion(self):
        monthly = CreditorCalculator.annual_to_periodic(0.03, ProjectionFrequency.MONTHLY)
        assert monthly > 0
        assert monthly < 0.03

    def test_annual_to_quarterly_conversion(self):
        quarterly = CreditorCalculator.annual_to_periodic(0.03, ProjectionFrequency.QUARTERLY)
        assert quarterly > 0
        assert quarterly < 0.03
        assert quarterly > CreditorCalculator.annual_to_periodic(0.03, ProjectionFrequency.MONTHLY)

    def test_annual_to_annual_conversion(self):
        annual = CreditorCalculator.annual_to_periodic(0.03, ProjectionFrequency.ANNUAL)
        assert annual == pytest.approx(0.03)

    def test_unknown_strategy_raises(self):
        config = CreditorConfig(strategy="indexed")
        with pytest.raises(ValueError, match="Unknown crediting strategy"):
            CreditorCalculator.get_annual_crediting_rate(config)

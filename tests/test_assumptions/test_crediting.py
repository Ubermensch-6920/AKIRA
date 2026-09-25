"""Tests for interest crediting configuration."""

from actuarial_model.assumptions.sets import CreditorConfig, FixedCreditingConfig


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

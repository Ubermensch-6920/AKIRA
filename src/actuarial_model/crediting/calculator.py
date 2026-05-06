"""Interest crediting calculation engine for policy projections."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from actuarial_model.assumptions.sets import CreditorConfig
    from actuarial_model.mortality.decrements import ProjectionFrequency


class CreditorCalculator:
    """Calculates interest crediting accrual for policy projections."""

    @staticmethod
    def get_annual_crediting_rate(config: "CreditorConfig", policy_year: int = 1) -> float:
        """Get annual crediting rate.

        Extensible for future indexed/hybrid strategies. Currently supports fixed rates.
        """
        if config.strategy == "fixed":
            return config.fixed.annual_rate
        raise ValueError(f"Unknown crediting strategy: {config.strategy}")

    @staticmethod
    def crediting_accrual(
        inforce_start: float,
        config: "CreditorConfig",
        policy_year: int = 1,
    ) -> float:
        """Calculate crediting accrual (positive, unlike decrements).

        Args:
            inforce_start: In-force count at start of period
            config: Creditor configuration
            policy_year: Policy duration (in years) for rate selection

        Returns:
            Crediting accrual amount (positive)
        """
        if not config.is_active:
            return 0.0
        rate = CreditorCalculator.get_annual_crediting_rate(config, policy_year)
        return inforce_start * rate

    @staticmethod
    def annual_to_periodic(annual_rate: float, frequency: "ProjectionFrequency") -> float:
        """Convert annual crediting rate to periodic (monthly/quarterly).

        Uses the compound interest formula: periodic_rate = 1 - (1 - annual_rate)^(1/periods)
        """
        periods_per_year = frequency.periods_per_year
        return 1 - ((1 - annual_rate) ** (1 / periods_per_year))

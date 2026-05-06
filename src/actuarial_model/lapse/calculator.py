"""Lapse decrement calculations."""

from typing import TYPE_CHECKING

from .rates import LapseRateTable

if TYPE_CHECKING:
    from actuarial_model.mortality.decrements import ProjectionFrequency


class LapseDecrementCalculator:
    """Calculates lapse decrements for policy projections."""

    @staticmethod
    def get_annual_decrement(
        rate_table: LapseRateTable, policy_duration_years: int
    ) -> float:
        """Get annual lapse rate for given policy duration.

        Args:
            rate_table: LapseRateTable containing base and shock rates.
            policy_duration_years: Policy duration in years (1+).

        Returns:
            Annual lapse rate (0.0 to 1.0).
        """
        return rate_table.rate_at_duration(policy_duration_years)

    @staticmethod
    def annual_to_periodic(
        annual_rate: float, frequency: "ProjectionFrequency"
    ) -> float:
        """Convert annual lapse rate to periodic using compound formula.

        periodic = 1 - (1 - annual)^(1/periods_per_year)
        """
        if not 0 <= annual_rate <= 1:
            raise ValueError("annual_rate must be between 0 and 1")
        return 1 - ((1 - annual_rate) ** (1 / frequency.periods_per_year))

    @staticmethod
    def annual_to_monthly(annual_rate: float) -> float:
        """Convert annual lapse rate to monthly."""
        from actuarial_model.mortality.decrements import ProjectionFrequency

        return LapseDecrementCalculator.annual_to_periodic(
            annual_rate, ProjectionFrequency.MONTHLY
        )

    @staticmethod
    def annual_to_quarterly(annual_rate: float) -> float:
        """Convert annual lapse rate to quarterly."""
        from actuarial_model.mortality.decrements import ProjectionFrequency

        return LapseDecrementCalculator.annual_to_periodic(
            annual_rate, ProjectionFrequency.QUARTERLY
        )

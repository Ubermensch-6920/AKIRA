"""Lapse decrement calculations."""

from .rates import LapseRateTable


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
    def annual_to_monthly(annual_rate: float) -> float:
        """Convert annual lapse rate to monthly.

        Uses the formula: monthly = 1 - (1 - annual)^(1/12).

        Args:
            annual_rate: Annual lapse rate (0.0 to 1.0).

        Returns:
            Monthly lapse rate (0.0 to 1.0).
        """
        if not 0 <= annual_rate <= 1:
            raise ValueError("annual_rate must be between 0 and 1")
        return 1 - ((1 - annual_rate) ** (1 / 12))

    @staticmethod
    def annual_to_quarterly(annual_rate: float) -> float:
        """Convert annual lapse rate to quarterly.

        Uses the formula: quarterly = 1 - (1 - annual)^(1/4).

        Args:
            annual_rate: Annual lapse rate (0.0 to 1.0).

        Returns:
            Quarterly lapse rate (0.0 to 1.0).
        """
        if not 0 <= annual_rate <= 1:
            raise ValueError("annual_rate must be between 0 and 1")
        return 1 - ((1 - annual_rate) ** (1 / 4))

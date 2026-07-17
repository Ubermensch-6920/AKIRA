"""Withdrawal decrement and surrender charge calculations."""

from .rates import FreeWithdrawalConfig, MvaConfig, PartialWithdrawalTable, SurrenderChargeSchedule


class WithdrawalCalculator:
    """
    Calculates withdrawal-related amounts for a single policy period.

    Withdrawal hierarchy (applied in order):
      1. Free withdrawal — no surrender charge or MVA
      2. Excess withdrawal — subject to surrender charge and MVA
      3. Full surrender — entire accumulated value, surrender charge + MVA on excess
    """

    @staticmethod
    def free_withdrawal_amount(
        accumulated_value: float,
        config: FreeWithdrawalConfig,
        policy_year: int,
        credited_rate: float = 0.0,
    ) -> float:
        """Annual free withdrawal allowance for the policy.

        Args:
            accumulated_value: Policy account value at start of period.
            config: Free withdrawal configuration.
            policy_year: Current policy year (1-based).
            credited_rate: The contract's fixed strategy rate — used only
                when ``config.basis`` is ``INTEREST_EARNED`` (MaxRate),
                where the free amount is the interest earned rather than
                a flat percentage of accumulated value.

        Returns:
            Maximum amount that can be withdrawn without charge.
        """
        if policy_year < config.applies_from_year:
            return 0.0
        if config.basis == "INTEREST_EARNED":
            return accumulated_value * credited_rate
        return accumulated_value * config.annual_free_pct

    @staticmethod
    def surrender_charge_amount(
        excess_withdrawal: float,
        policy_year: int,
        schedule: SurrenderChargeSchedule,
    ) -> float:
        """Surrender charge on the portion of withdrawal exceeding free amount.

        Args:
            excess_withdrawal: Amount withdrawn beyond free-withdrawal allowance.
            policy_year: Current policy year (1-based).
            schedule: Surrender charge schedule for the product.

        Returns:
            Dollar amount of surrender charge (reduces net proceeds).
        """
        rate = schedule.charge_at_year(policy_year)
        return excess_withdrawal * rate

    @staticmethod
    def mva_amount(
        excess_withdrawal: float,
        rate_change_bps: float,
        config: MvaConfig,
    ) -> float:
        """Market Value Adjustment on the excess withdrawal amount.

        A negative return means MVA reduces proceeds (rates rose since issue).
        A positive return means MVA increases proceeds (rates fell since issue).

        Args:
            excess_withdrawal: Amount withdrawn beyond free-withdrawal allowance.
            rate_change_bps: Change in reference rate since issue, in basis points.
            config: MVA configuration.

        Returns:
            Dollar MVA adjustment (can be negative or positive).
        """
        if not config.is_active or excess_withdrawal <= 0:
            return 0.0
        rate = config.adjustment_rate(rate_change_bps)
        return excess_withdrawal * rate

    @staticmethod
    def net_withdrawal_proceeds(
        requested_withdrawal: float,
        accumulated_value: float,
        policy_year: int,
        free_config: FreeWithdrawalConfig,
        schedule: SurrenderChargeSchedule,
        mva_config: MvaConfig,
        rate_change_bps: float = 0.0,
    ) -> dict[str, float]:
        """Compute all components of a withdrawal transaction.

        Splits the requested amount into free and excess portions, then
        applies surrender charge and MVA to the excess portion only.

        Args:
            requested_withdrawal: Total amount requested by policyholder.
            accumulated_value: Account value at start of period.
            policy_year: Current policy year (1-based).
            free_config: Free withdrawal configuration.
            schedule: Surrender charge schedule.
            mva_config: MVA configuration.
            rate_change_bps: Basis point change in reference rate since issue.

        Returns:
            Dict with keys: free_amount, excess_amount, surrender_charge,
            mva_adjustment, net_proceeds, gross_withdrawal.
        """
        free_allowance = WithdrawalCalculator.free_withdrawal_amount(
            accumulated_value, free_config, policy_year
        )
        free_amount = min(requested_withdrawal, free_allowance)
        excess_amount = max(requested_withdrawal - free_allowance, 0.0)

        sc = WithdrawalCalculator.surrender_charge_amount(excess_amount, policy_year, schedule)
        mva = WithdrawalCalculator.mva_amount(excess_amount, rate_change_bps, mva_config)

        net_proceeds = free_amount + excess_amount - sc + mva

        return {
            "free_amount": free_amount,
            "excess_amount": excess_amount,
            "surrender_charge": sc,
            "mva_adjustment": mva,
            "net_proceeds": net_proceeds,
            "gross_withdrawal": requested_withdrawal,
        }

    @staticmethod
    def partial_withdrawal_decrement(
        inforce: float,
        table: PartialWithdrawalTable,
        duration_years: int,
    ) -> float:
        """Number of policies (or policy count) expected to take a partial withdrawal.

        Args:
            inforce: Number of policies in force at start of period.
            table: Partial withdrawal rate table.
            duration_years: Policy duration in whole years.

        Returns:
            Expected count of partial-withdrawal events.
        """
        rate = table.rate_at_duration(duration_years)
        return inforce * rate

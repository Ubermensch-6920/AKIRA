"""
MYGA projection engine (Phase 1).

Projects per-policy MYGA cash flows: account-value roll-forward at the
guaranteed rate, surrender / death decrements, MVA where applicable, and
end-of-guarantee disposition. Outputs the gross cash-flow streams that
feed BEL discounting and every framework reserve module.

Design — two layers:
  Layer 1 (existing): MortalityDecrementCalculator produces per-period
    inforce counts and decrement amounts (mortality, lapse).
  Layer 2 (this module): AV roll-forward converts those counts into dollars
    using the policy's guaranteed_rate, surrender charge schedule, and
    death-benefit basis. Partial withdrawals live entirely in this layer:
    they reduce account value, not policy count, so they are deliberately
    NOT passed to the decrement engine (which models withdrawal_decrement
    as a termination).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from ...assumptions.sets import AssumptionSet, WithdrawalAssumptions
from ...crediting.calculator import CreditorCalculator
from ...lapse.calculator import LapseDecrementCalculator
from ...models.cash_flows import GrossCashFlows, MygaCashFlowRecord, PolicyCashFlows
from ...models.policy import MygaPolicyState
from ...mortality.decrements import (
    AssumptionSelection,
    MortalityAssumptionRepository,
    MortalityDecrementCalculator,
    MortalityProjectionRequest,
    MortalityProjectionRow,
    ProjectionFrequency,
    SeriatimLifeInput,
    SeriatimPolicyInput,
    Sex,
)
from ...withdrawal.rates import SurrenderChargeRepository, SurrenderChargeSchedule

_SURRENDER_REPO = SurrenderChargeRepository.with_athene_schedules()


class MygaProjectionInput(BaseModel):
    """Inputs to the MYGA projection engine."""

    assumption_set: AssumptionSet
    policies: list[MygaPolicyState]
    valuation_date: date | None = None
    projection_horizon_years: int = 30


class MygaProjectionOutput(BaseModel):
    """MYGA gross per-policy cash flow streams."""

    cash_flows: GrossCashFlows | None = None


class MygaProjectionEngine:
    """
    MYGA cash flow projection engine.

    Coordinates the existing decrement calculators (mortality, lapse, withdrawal)
    with an AV roll-forward to produce per-period gross cash flows.

    Usage:
        engine = MygaProjectionEngine(MortalityAssumptionRepository.with_embedded_soa_iam_g2())
        cf = engine.project_policy(policy, assumption_set, horizon_years=30)
    """

    methodology_version = "myga_projection_v0.1.0"

    def __init__(self, mortality_repository: MortalityAssumptionRepository) -> None:
        self._mortality_calc = MortalityDecrementCalculator(mortality_repository)

    def project_policy(
        self,
        policy: MygaPolicyState,
        assumption_set: AssumptionSet,
        horizon_years: int,
        frequency: ProjectionFrequency = ProjectionFrequency.MONTHLY,
        run_id: str = "UNNAMED_RUN",
    ) -> PolicyCashFlows:
        """Project a single MYGA policy's gross cash flows.

        Args:
            policy: Per-policy state (AV, guaranteed rate, guarantee term, etc.)
            assumption_set: Master assumption configuration (lapse, withdrawal basis).
            horizon_years: Maximum projection length in years.
            frequency: Projection timestep (monthly by default for Phase 1).
            run_id: Identifier stamped on each decrement row.

        Returns:
            PolicyCashFlows with one MygaCashFlowRecord per projected period.
        """
        n_periods = horizon_years * frequency.periods_per_year
        mort_request = self._build_mortality_request(
            policy, assumption_set, n_periods, frequency, run_id
        )
        mort_output = self._mortality_calc.calculate(mort_request)

        proj = assumption_set.stat_carvm
        withdrawal_cfg = proj.withdrawal if proj.withdrawal.is_active else None
        surrender_schedule = _resolve_surrender_schedule(policy)
        records = self._project_cash_flows(
            policy, mort_output.records, frequency, surrender_schedule, withdrawal_cfg
        )
        return PolicyCashFlows(policy_id=policy.policy_id, records=records)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_mortality_request(
        self,
        policy: MygaPolicyState,
        assumption_set: AssumptionSet,
        n_periods: int,
        frequency: ProjectionFrequency,
        run_id: str,
    ) -> MortalityProjectionRequest:
        # Use stat_carvm as the Phase 1 projection basis.
        proj = assumption_set.stat_carvm
        return MortalityProjectionRequest(
            run_id=run_id,
            seriatim=SeriatimPolicyInput(
                policy_id=policy.policy_id,
                issue_date=policy.issue_date,
                starting_policy_count=1.0,
                lives=[
                    SeriatimLifeInput(
                        life_id=f"{policy.policy_id}_L1",
                        issue_age=float(policy.issue_age),
                        sex=Sex(policy.sex),
                    )
                ],
            ),
            assumptions=AssumptionSelection(
                assumption_set_id=assumption_set.assumption_set_id,
                lapse_rate_table=(
                    proj.lapse_config if proj.lapse_config.is_active else None
                ),
                # Partial withdrawals reduce AV, not policy count — handled in
                # the AV layer. The decrement engine models withdrawal_decrement
                # as a termination, which would leak the unwithdrawn 90% of AV.
                withdrawal_assumptions=None,
                # AV crediting is handled below; do not double-apply via
                # the mortality engine's crediting_accrual path.
                creditor_config=None,
            ),
            projection_periods=n_periods,
            frequency=frequency,
        )

    def _project_cash_flows(
        self,
        policy: MygaPolicyState,
        mort_rows: list[MortalityProjectionRow],
        frequency: ProjectionFrequency,
        surrender_schedule: SurrenderChargeSchedule | None,
        withdrawal_cfg: WithdrawalAssumptions | None,
    ) -> list[MygaCashFlowRecord]:
        """Layer AV roll-forward on top of the decrement schedule."""

        av_per_policy = policy.account_value
        periodic_rate = CreditorCalculator.annual_to_periodic(
            policy.guaranteed_rate, frequency
        )
        periods_per_year = frequency.periods_per_year
        maturity_triggered = False
        records: list[MygaCashFlowRecord] = []

        for row in mort_rows:
            inforce_bop = row.single_inforce_start or 0.0
            if inforce_bop <= 0.0 or maturity_triggered:
                break

            # ── Interest ─────────────────────────────────────────────────────
            av_bop = av_per_policy
            interest_per_policy = av_bop * periodic_rate
            av_mid = av_bop + interest_per_policy
            interest_credited = inforce_bop * interest_per_policy

            policy_year = (row.period - 1) // periods_per_year + 1

            # ── Death benefit (ROAV or ROP) ───────────────────────────────────
            mort_dec = row.single_mortality_decrement or 0.0
            if policy.death_benefit_basis == "ROP":
                db_per_policy = max(policy.single_premium, av_mid)
            else:  # ROAV (default) — return of account value
                db_per_policy = av_mid
            death_benefits = mort_dec * db_per_policy

            # ── Surrender / lapse benefit ─────────────────────────────────────
            lapse_dec = row.single_lapse_decrement or 0.0
            sc_rate = (
                surrender_schedule.charge_at_year(policy_year)
                if surrender_schedule else 0.0
            )
            sc_per_policy = av_mid * sc_rate
            # Phase 1: no interest-rate path → MVA = 0 throughout
            net_sv_per_policy = av_mid - sc_per_policy
            surrender_benefits = lapse_dec * net_sv_per_policy
            surrender_charge = lapse_dec * sc_per_policy
            mva_adjustment = 0.0

            # ── Partial withdrawals ───────────────────────────────────────────
            # A fraction of in-force policyholders takes a free withdrawal of
            # free_withdrawal_pct × AV each period. This drains AV but does NOT
            # terminate the policy, so it never touches the inforce count.
            period_w_rate = 0.0
            if withdrawal_cfg is not None:
                annual_w_rate = withdrawal_cfg.partial_withdrawal.rate_at_duration(
                    policy_year
                )
                period_w_rate = LapseDecrementCalculator.annual_to_periodic(
                    annual_w_rate, frequency
                )
            withdrawal_drain = av_mid * policy.free_withdrawal_pct * period_w_rate
            partial_withdrawals = inforce_bop * withdrawal_drain

            # ── Maturity: pay out remaining AV at guarantee end ───────────────
            inforce_eop = row.single_inforce_end or 0.0
            maturity_benefits = 0.0
            if row.period_end_date >= policy.guarantee_end_date:
                maturity_benefits = inforce_eop * av_mid
                inforce_eop = 0.0
                maturity_triggered = True

            # ── AV EOP ───────────────────────────────────────────────────────
            av_per_policy = max(av_mid - withdrawal_drain, 0.0)
            account_value_eop = inforce_eop * av_per_policy

            records.append(
                MygaCashFlowRecord(
                    policy_id=policy.policy_id,
                    period=row.period,
                    period_start_date=row.period_start_date,
                    period_end_date=row.period_end_date,
                    account_value_bop=inforce_bop * av_bop,
                    interest_credited=interest_credited,
                    partial_withdrawals=partial_withdrawals,
                    surrender_charge=surrender_charge,
                    mva_adjustment=mva_adjustment,
                    surrender_benefits=surrender_benefits,
                    death_benefits=death_benefits,
                    maturity_benefits=maturity_benefits,
                    account_value_eop=account_value_eop,
                    lives_in_force=inforce_eop,
                )
            )

        return records


def _resolve_surrender_schedule(
    policy: MygaPolicyState,
) -> SurrenderChargeSchedule | None:
    """Look up the policy's surrender schedule from the embedded repository.

    Returns None if the schedule ID is not registered (treated as no charges).
    """
    try:
        return _SURRENDER_REPO.get(policy.surrender_charge_schedule_id)
    except ValueError:
        return None


def calculate(inputs: MygaProjectionInput) -> MygaProjectionOutput:
    """Project gross MYGA cash flows for every policy in ``inputs.policies``."""
    repository = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
    engine = MygaProjectionEngine(repository)

    valuation_date = inputs.valuation_date or date.today()
    frequency = ProjectionFrequency.MONTHLY

    policy_cash_flows = [
        engine.project_policy(
            policy=policy,
            assumption_set=inputs.assumption_set,
            horizon_years=inputs.projection_horizon_years,
            frequency=frequency,
        )
        for policy in inputs.policies
    ]

    return MygaProjectionOutput(
        cash_flows=GrossCashFlows(
            valuation_date=valuation_date,
            policies=policy_cash_flows,
        )
    )

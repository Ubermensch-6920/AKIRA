"""
MYGA projection model (gaspatchio).

Projects every MYGA policy at once on an ``ActuarialFrame``: one row per
policy, one list element per month of the shared valuation-date grid. There
is no per-policy or per-period Python loop — each line below is a whole
projection vector.

Sections:
  1. Time          — duration, policy year, attained age per period
  2. Mortality     — base qx x G2 x flat improvement → monthly qx (constant force)
  3. Lapse         — annual lapse by policy year (base + shocks) → monthly
  4. Withdrawals   — partial-withdrawal incidence x free-withdrawal %
  5. Account value — guaranteed crediting less withdrawals, per policy
  6. In force      — survivorship, masked at the end of the guarantee
  7. Cash flows    — interest, death, surrender, withdrawal, maturity, AV

Timing convention per period t (valuation + t months → + t+1 months):
  interest is credited on the BOP account value; deaths and surrenders
  (independent monthly rates applied to BOP in-force) are paid the
  mid-period account value (BOP + interest); survivors then take partial
  withdrawals; at the guarantee end date survivors mature on the
  post-withdrawal account value. The account-value roll-forward therefore
  balances exactly:

      AV_bop + interest = death + surrender + surrender charge
                          + withdrawals + maturity + AV_eop

Methodology changes vs. the pre-gaspatchio loop engine (``myga_projection_v0.1.0``):
  - Projection starts at the valuation date with the policy's current AV
    and in force = 1 (previously from issue date, with pre-valuation periods
    discarded — which misstated in-force policies).
  - Monthly crediting is ``(1 + i)^(1/12) - 1`` (previously
    ``1 - (1 - i)^(1/12)``, which over-credited: ~3.09% for a 3% guarantee).
  - Lapse uses policy year ``duration_months // 12 + 1`` (previously
    ``ceil(years_from_issue)``, which shifted shock years by one month).
  - Partial withdrawals are taken by survivors (previously by all BOP
    in force, so dying / surrendering policies received the withdrawal on
    top of the full account value), and maturity pays post-withdrawal AV.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import polars as pl
from gaspatchio import ActuarialFrame, when
from pydantic import BaseModel

from ...assumptions.mortality import MortalityAssumptionRepository
from ...assumptions.sets import ProjectionBasisConfig
from ...assumptions.withdrawal import SurrenderChargeRepository
from ...models.policy import MygaPolicyState
from ..grid import DAYS_PER_YEAR, ProjectionGrid, grid_vector
from ..model_points import myga_model_points
from ..projection import CASH_FLOW_COLUMNS, COUNT_COLUMNS, LABEL_COLUMNS, Projection
from ..tables import (
    MAX_TABLE_AGE,
    mortality_tables,
    policy_year_table,
    surrender_charge_table,
)

METHODOLOGY_VERSION = "myga_gaspatchio_v1.0.0"

_MORTALITY_REPO = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
_SURRENDER_REPO = SurrenderChargeRepository.with_athene_schedules()

# Diagnostic vectors kept when ``detail=True`` (for single-policy debugging).
DETAIL_COLUMNS = (
    "policy_year",
    "attained_age",
    "annual_qx",
    "monthly_qx",
    "annual_lapse_rate",
    "monthly_lapse_rate",
    "withdrawal_rate",
    "surrender_charge_rate",
    "av_bop_pp",
    "av_mid_pp",
    "av_eop_pp",
    "in_force_bop",
)


class MygaProjectionInput(BaseModel):
    """Inputs to the MYGA projection."""

    policies: list[MygaPolicyState]
    config: ProjectionBasisConfig
    valuation_date: date
    projection_horizon_years: int = 30


def build_frame(
    model_points: pl.DataFrame,
    config: ProjectionBasisConfig,
    grid: ProjectionGrid,
    *,
    mortality_repository: MortalityAssumptionRepository = _MORTALITY_REPO,
    surrender_repository: SurrenderChargeRepository = _SURRENDER_REPO,
) -> ActuarialFrame:
    """The MYGA gaspatchio model: model points in, lazily-defined projection out."""
    af = ActuarialFrame(model_points)

    # ── 1. Time ──────────────────────────────────────────────────────────
    af.t = grid_vector(grid.period_index, pl.Int64())
    af.duration_months = af.duration_months_at_valuation + af.t
    af.policy_year = af.duration_months // 12 + 1
    af.attained_age = (af.issue_age + af.duration_months // 12).clip(0, MAX_TABLE_AGE)

    # ── 2. Mortality ─────────────────────────────────────────────────────
    mort = config.mortality
    base_qx, g2_rate = mortality_tables(mort, mortality_repository)
    af.base_qx = base_qx.lookup(sex=af.sex, age=af.attained_age)
    af.g2_rate = g2_rate.lookup(sex=af.sex, age=af.attained_age)
    # Improvement clocks: G2 from its table base date; the flat overlay from issue.
    af.years_since_g2_base = grid_vector(
        [max(y, 0.0) for y in grid.years_since(mort.g2_base_date)], pl.Float64()
    )
    af.days_from_valuation = grid_vector(grid.days_from_valuation(), pl.Float64())
    af.years_since_issue = (
        (af.days_from_valuation + af.days_since_issue_at_valuation) / DAYS_PER_YEAR
    ).clip(lower_bound=0.0)
    af.annual_qx = (
        af.base_qx
        * mort.mortality_multiplier
        * (1.0 - af.g2_rate * mort.g2_scale_multiplier) ** af.years_since_g2_base
        * (1.0 - mort.flat_improvement_rate) ** af.years_since_issue
    ).clip(0.0, 1.0)
    af.monthly_qx = 1.0 - (1.0 - af.annual_qx) ** (1.0 / 12.0)

    # ── 3. Lapse ─────────────────────────────────────────────────────────
    lapse = config.lapse_config
    if lapse.is_active:
        shock_table = policy_year_table("lapse", lapse.shock_rates, lapse.base_annual_rate)
        af.annual_lapse_rate = (
            shock_table.lookup(policy_year=af.policy_year)
            if shock_table is not None
            else (af.t * 0.0 + lapse.base_annual_rate)
        )
    else:
        af.annual_lapse_rate = af.t * 0.0
    af.monthly_lapse_rate = 1.0 - (1.0 - af.annual_lapse_rate) ** (1.0 / 12.0)

    # ── 4. Withdrawals ───────────────────────────────────────────────────
    withdrawal = config.withdrawal
    if withdrawal.is_active:
        partial = withdrawal.partial_withdrawal
        incidence_table = policy_year_table(
            "withdrawal", partial.rates_by_duration, partial.base_annual_rate
        )
        af.annual_withdrawal_incidence = (
            incidence_table.lookup(policy_year=af.policy_year)
            if incidence_table is not None
            else (af.t * 0.0 + partial.base_annual_rate)
        )
        af.withdrawal_rate = af.free_withdrawal_pct * (
            1.0 - (1.0 - af.annual_withdrawal_incidence) ** (1.0 / 12.0)
        )
    else:
        af.withdrawal_rate = af.t * 0.0

    # ── 5. Account value (per policy) ────────────────────────────────────
    af.monthly_credit_rate = (1.0 + af.guaranteed_rate) ** (1.0 / 12.0) - 1.0
    af.av_growth = (1.0 + af.monthly_credit_rate) * (1.0 - af.withdrawal_rate)
    af.av_bop_pp = af.account_value * af.av_growth.cum_prod().projection.previous_period(
        fill_value=1.0
    )
    af.av_mid_pp = af.av_bop_pp * (1.0 + af.monthly_credit_rate)
    af.av_eop_pp = af.av_mid_pp * (1.0 - af.withdrawal_rate)

    # ── 6. In force ──────────────────────────────────────────────────────
    af.survival = (1.0 - af.monthly_qx - af.monthly_lapse_rate).clip(lower_bound=0.0)
    af.active = when(af.t <= af.maturity_period).then(1.0).otherwise(0.0)
    af.in_force_bop = (
        af.survival.cum_prod().projection.previous_period(fill_value=1.0) * af.active
    )
    af.deaths = af.in_force_bop * af.monthly_qx
    af.surrenders = af.in_force_bop * af.monthly_lapse_rate
    af.survivors = af.in_force_bop * af.survival
    af.is_maturity = when(af.t == af.maturity_period).then(1.0).otherwise(0.0)

    # ── 7. Cash flows ────────────────────────────────────────────────────
    af.surrender_charge_rate = surrender_charge_table(surrender_repository).lookup(
        surrender_charge_schedule_id=af.surrender_charge_schedule_id,
        policy_year=af.policy_year,
    )
    af.death_benefit_pp = (
        when((af.death_benefit_basis == "ROP") & (af.av_mid_pp < af.single_premium))
        .then(af.single_premium)
        .otherwise(af.av_mid_pp)
    )

    af.account_value_bop = af.in_force_bop * af.av_bop_pp
    af.interest_credited = af.account_value_bop * af.monthly_credit_rate
    af.death_benefits = af.deaths * af.death_benefit_pp
    af.surrender_charge = af.surrenders * af.av_mid_pp * af.surrender_charge_rate
    af.surrender_benefits = af.surrenders * af.av_mid_pp * (1.0 - af.surrender_charge_rate)
    af.mva_adjustment = af.t * 0.0  # MVA needs an interest-rate path (not yet wired)
    af.partial_withdrawals = af.survivors * af.av_mid_pp * af.withdrawal_rate
    af.maturity_benefits = af.survivors * af.is_maturity * af.av_eop_pp
    af.lives_in_force = af.survivors * (1.0 - af.is_maturity)
    af.account_value_eop = af.lives_in_force * af.av_eop_pp
    return af


def project(
    policies: Sequence[MygaPolicyState],
    config: ProjectionBasisConfig,
    valuation_date: date,
    *,
    projection_horizon_years: int = 30,
    detail: bool = False,
) -> Projection:
    """Project MYGA policies on ``config`` from ``valuation_date``.

    Args:
        policies: MYGA seriatim records.
        config: The framework config block whose projection assumptions apply.
        valuation_date: Projection start; period 0 begins here.
        projection_horizon_years: Grid length; cash flows past it are truncated.
        detail: Keep diagnostic vectors (rates, per-policy AV) in the frame.
    """
    grid = ProjectionGrid.from_horizon(valuation_date, projection_horizon_years)
    if not policies:
        return Projection.empty(grid, METHODOLOGY_VERSION)

    model_points = myga_model_points(policies, valuation_date)
    frame = build_frame(model_points, config, grid).collect()
    keep = [*LABEL_COLUMNS, "reinsurance_treaty_id", *CASH_FLOW_COLUMNS, *COUNT_COLUMNS]
    if detail:
        keep += list(DETAIL_COLUMNS)
    return Projection(grid=grid, frame=frame.select(keep), methodology_version=METHODOLOGY_VERSION)


def calculate(inputs: MygaProjectionInput) -> Projection:
    """Validated-input entry point (see :func:`project`)."""
    return project(
        inputs.policies,
        inputs.config,
        inputs.valuation_date,
        projection_horizon_years=inputs.projection_horizon_years,
    )

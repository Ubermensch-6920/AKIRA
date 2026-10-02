"""
Hand-built MYGA projection (NumPy).

YOU WRITE: every function marked ``TODO (hand-build)``. Each docstring gives
the formula, the array shapes, and the test that checks it. The wiring in
:func:`project` (bottom of file) is already done — it calls your functions
in order, so once they all pass, the full engine runs.

Conventions (same as the gaspatchio benchmark, see ARCHITECTURE.md §3):
  - Arrays are (P, T): P policies x T monthly periods. Period t runs from
    valuation + t months to valuation + t+1 months.
  - Deaths and surrenders use independent monthly rates on BOP in force and
    are paid the mid-period account value (BOP + interest).
  - Survivors then take partial withdrawals; at the guarantee end date the
    survivors mature on the post-withdrawal account value.

Run your tests:  pytest handbuilt -rs
(an unbuilt function shows as SKIPPED "TODO", a built one as PASSED)
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import numpy as np

from actuarial_model.assumptions.sets import MortalityConfig, ProjectionBasisConfig
from actuarial_model.engine.grid import ProjectionGrid
from actuarial_model.engine.projection import Projection
from actuarial_model.models.policy import MygaPolicyState

from . import inputs

METHODOLOGY_VERSION = "myga_handbuilt_v0.1.0"


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Time
# ─────────────────────────────────────────────────────────────────────────────


def duration_and_policy_year(
    duration_months_at_valuation: np.ndarray, n_periods: int
) -> tuple[np.ndarray, np.ndarray]:
    """Months since issue and policy year at the start of every period.

        duration_months[p, t] = duration_months_at_valuation[p] + t
        policy_year[p, t]     = duration_months[p, t] // 12 + 1

    Args:
        duration_months_at_valuation: (P,) int — whole months from issue to valuation.
        n_periods: T.

    Returns:
        (duration_months, policy_year), both (P, T) int.

    Test: test_step1_duration_and_policy_year
    """
    raise NotImplementedError("Step 1: duration_and_policy_year")


def attained_age(issue_age: np.ndarray, duration_months: np.ndarray, max_age: int) -> np.ndarray:
    """Age last birthday-style attained age, clipped to the table range.

        attained_age[p, t] = clip(issue_age[p] + duration_months[p, t] // 12, 0, max_age)

    Args:
        issue_age: (P,) int.
        duration_months: (P, T) int.
        max_age: last age in the mortality tables.

    Returns:
        (P, T) int.

    Test: test_step1_attained_age
    """
    raise NotImplementedError("Step 1: attained_age")


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Rate conversions
# ─────────────────────────────────────────────────────────────────────────────


def annual_to_monthly_decrement(annual_rate: np.ndarray | float) -> np.ndarray:
    """Annual decrement probability → monthly, constant force within the year.

        q_monthly = 1 - (1 - q_annual) ** (1/12)

    Works element-wise on any shape (and on a plain float).

    Test: test_step2_annual_to_monthly_decrement
    """
    raise NotImplementedError("Step 2: annual_to_monthly_decrement")


def monthly_credit_rate(guaranteed_rate: np.ndarray) -> np.ndarray:
    """Annual effective guaranteed crediting rate → monthly effective.

        i_monthly = (1 + i_annual) ** (1/12) - 1

    Note this is NOT the decrement formula above — interest compounds up,
    decrements compound survival down. (The old loop engine used the
    decrement formula here and over-credited.)

    Args:
        guaranteed_rate: (P,).

    Returns:
        (P,).

    Test: test_step2_monthly_credit_rate
    """
    raise NotImplementedError("Step 2: monthly_credit_rate")


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Policy-year rate lookup (used for lapse AND partial withdrawals)
# ─────────────────────────────────────────────────────────────────────────────


def rate_by_policy_year(
    policy_year: np.ndarray, default_rate: float, overrides: dict[int, float]
) -> np.ndarray:
    """Annual rate for each cell: ``overrides[year]`` where listed, else ``default_rate``.

    Example: default 0.02, overrides {3: 0.20, 5: 0.40}
        policy_year [[1, 2, 3, 4, 5, 6]] → [[0.02, 0.02, 0.20, 0.02, 0.40, 0.02]]

    Args:
        policy_year: (P, T) int.
        default_rate: base annual rate.
        overrides: shock / duration-specific annual rates keyed by policy year.

    Returns:
        (P, T) float.

    Test: test_step3_rate_by_policy_year
    """
    raise NotImplementedError("Step 3: rate_by_policy_year")


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Mortality
# ─────────────────────────────────────────────────────────────────────────────


def adjusted_annual_qx(
    base_qx: np.ndarray,
    g2_rate: np.ndarray,
    years_since_g2_base: np.ndarray,
    years_since_issue: np.ndarray,
    mortality: MortalityConfig,
) -> np.ndarray:
    """Base table improved by G2 and a flat overlay, clipped to [0, 1].

        qx = base_qx
             * mortality.mortality_multiplier
             * (1 - g2_rate * mortality.g2_scale_multiplier) ** years_since_g2_base
             * (1 - mortality.flat_improvement_rate) ** years_since_issue

    Args:
        base_qx, g2_rate: (P, T).
        years_since_g2_base: (T,) — same for every policy (broadcasts).
        years_since_issue: (P, T).
        mortality: the basis's MortalityConfig.

    Returns:
        (P, T) annual qx.

    Test: test_step4_adjusted_annual_qx
    """
    raise NotImplementedError("Step 4: adjusted_annual_qx")


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — In force (the core of the engine)
# ─────────────────────────────────────────────────────────────────────────────


def in_force(
    monthly_qx: np.ndarray,
    monthly_lapse: np.ndarray,
    maturity_period: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Beginning-of-period in force and end-of-period survivors, per unit policy.

        survival[p, t]     = max(1 - q[p, t] - l[p, t], 0)
        in_force_bop[p, 0] = 1
        in_force_bop[p, t] = in_force_bop[p, t-1] * survival[p, t-1]      (t >= 1)
        in_force_bop[p, t] = 0  for every t > maturity_period[p]
        survivors[p, t]    = in_force_bop[p, t] * survival[p, t]

    No Python loop over policies is needed; one over t is acceptable as a
    first version, but try to get there with a cumulative product.

    Args:
        monthly_qx, monthly_lapse: (P, T).
        maturity_period: (P,) int — last period the policy is in force.

    Returns:
        (in_force_bop, survivors), both (P, T).

    Test: test_step5_in_force_*
    """
    raise NotImplementedError("Step 5: in_force")


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Account value per policy
# ─────────────────────────────────────────────────────────────────────────────


def account_value_per_policy(
    account_value: np.ndarray,
    monthly_credit: np.ndarray,
    withdrawal_rate: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-policy account value at BOP, mid-period and EOP.

        av_bop[p, 0] = account_value[p]
        av_mid[p, t] = av_bop[p, t] * (1 + i[p])                 interest credited
        av_eop[p, t] = av_mid[p, t] * (1 - w[p, t])              survivors' withdrawal
        av_bop[p, t] = av_eop[p, t-1]                           (t >= 1)

    Args:
        account_value: (P,) AV at valuation.
        monthly_credit: (P,) from Step 2.
        withdrawal_rate: (P, T) fraction of AV withdrawn per month.

    Returns:
        (av_bop, av_mid, av_eop), each (P, T).

    Test: test_step6_account_value_per_policy
    """
    raise NotImplementedError("Step 6: account_value_per_policy")


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 (next session) — Cash flows
# ─────────────────────────────────────────────────────────────────────────────


def cash_flows(
    *,
    in_force_bop: np.ndarray,
    survivors: np.ndarray,
    monthly_qx: np.ndarray,
    monthly_lapse: np.ndarray,
    av_bop: np.ndarray,
    av_mid: np.ndarray,
    av_eop: np.ndarray,
    monthly_credit: np.ndarray,
    withdrawal_rate: np.ndarray,
    surrender_charge_rate: np.ndarray,
    single_premium: np.ndarray,
    death_benefit_is_rop: np.ndarray,
    maturity_period: np.ndarray,
) -> dict[str, np.ndarray]:
    """All projected cash-flow lines, each (P, T). Keys and formulas:

        account_value_bop   = in_force_bop * av_bop
        interest_credited   = in_force_bop * av_bop * i
        death_benefits      = in_force_bop * q * DB,  DB = max(single_premium, av_mid) if ROP else av_mid
        surrender_benefits  = in_force_bop * l * av_mid * (1 - sc)
        surrender_charge    = in_force_bop * l * av_mid * sc
        mva_adjustment      = 0
        partial_withdrawals = survivors * av_mid * w
        maturity_benefits   = survivors * av_eop        only where t == maturity_period
        lives_in_force      = survivors                 except 0 where t == maturity_period
        account_value_eop   = lives_in_force * av_eop

    Check: AV_bop + interest == death (at AV) + surrender + charge
           + withdrawals + maturity + AV_eop, every cell.

    Test: test_step7_cash_flows, then test_reconciles_to_gaspatchio
    """
    raise NotImplementedError("Step 7: cash_flows")


# ─────────────────────────────────────────────────────────────────────────────
# Wiring (provided) — calls the steps above in order
# ─────────────────────────────────────────────────────────────────────────────


def project(
    policies: Sequence[MygaPolicyState],
    config: ProjectionBasisConfig,
    valuation_date: date,
    *,
    projection_horizon_years: int = 30,
) -> Projection:
    """Project MYGA policies with the hand-built engine (same contract as the benchmark)."""
    grid = ProjectionGrid.from_horizon(valuation_date, projection_horizon_years)
    if not policies:
        return Projection.empty(grid, METHODOLOGY_VERSION)
    pa = inputs.policy_arrays(policies, valuation_date)
    n_periods = grid.n_periods

    # Step 1
    duration_months, policy_year = duration_and_policy_year(pa.duration_months_at_valuation, n_periods)
    age = attained_age(pa.issue_age, duration_months, inputs.MAX_AGE)

    # Step 4 (inputs from plumbing)
    base_qx, g2_rate = inputs.mortality_rates(config.mortality, pa.sex, age)
    years_g2, years_issue = inputs.improvement_clocks(
        grid, config.mortality, pa.days_since_issue_at_valuation
    )
    q = annual_to_monthly_decrement(
        adjusted_annual_qx(base_qx, g2_rate, years_g2, years_issue, config.mortality)
    )

    # Step 3 — lapse
    lapse = config.lapse_config
    annual_lapse = (
        rate_by_policy_year(policy_year, lapse.base_annual_rate, lapse.shock_rates)
        if lapse.is_active
        else np.zeros((pa.n_policies, n_periods))
    )
    l_m = annual_to_monthly_decrement(annual_lapse)

    # Step 3 — partial withdrawals (incidence x free-withdrawal %)
    wd = config.withdrawal
    if wd.is_active:
        incidence = rate_by_policy_year(
            policy_year,
            wd.partial_withdrawal.base_annual_rate,
            wd.partial_withdrawal.rates_by_duration,
        )
        w = pa.free_withdrawal_pct[:, None] * annual_to_monthly_decrement(incidence)
    else:
        w = np.zeros((pa.n_policies, n_periods))

    # Steps 2, 5, 6
    i_m = monthly_credit_rate(pa.guaranteed_rate)
    in_force_bop, survivors = in_force(q, l_m, pa.maturity_period)
    av_bop, av_mid, av_eop = account_value_per_policy(pa.account_value, i_m, w)

    # Step 7
    flows = cash_flows(
        in_force_bop=in_force_bop,
        survivors=survivors,
        monthly_qx=q,
        monthly_lapse=l_m,
        av_bop=av_bop,
        av_mid=av_mid,
        av_eop=av_eop,
        monthly_credit=i_m,
        withdrawal_rate=w,
        surrender_charge_rate=inputs.surrender_charge_rates(
            pa.surrender_charge_schedule_id, policy_year
        ),
        single_premium=pa.single_premium,
        death_benefit_is_rop=pa.death_benefit_is_rop,
        maturity_period=pa.maturity_period,
    )
    return inputs.to_projection(grid, pa.labels, flows, METHODOLOGY_VERSION)

"""Tests for the gaspatchio MYGA projection.

The central test reconciles the vectorised gaspatchio model against an
independent scalar reference — a plain month-by-month loop written from the
methodology in the module docstring — across a mixed portfolio (in-force and
new business, ROP and ROAV, shocked lapse, charge schedules, sexes).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from dateutil.relativedelta import relativedelta

from actuarial_model.assumptions.lapse import LapseRateTable
from actuarial_model.assumptions.mortality import MortalityAssumptionRepository
from actuarial_model.assumptions.sets import ProjectionBasisConfig
from actuarial_model.assumptions.withdrawal import (
    PartialWithdrawalTable,
    SurrenderChargeRepository,
)
from actuarial_model.engine.projection import CASH_FLOW_COLUMNS, OUTFLOW_COLUMNS
from actuarial_model.engine.projections import myga
from tests.factories import VAL_DATE, policy

HORIZON_YEARS = 12
_MORT = MortalityAssumptionRepository.with_embedded_soa_iam_g2()
_SC = SurrenderChargeRepository.with_athene_schedules()


def _config(**overrides) -> ProjectionBasisConfig:
    config = ProjectionBasisConfig(
        lapse_config=LapseRateTable(
            table_id="shock", base_annual_rate=0.02, shock_rates={3: 0.20, 5: 0.40}
        )
    )
    config.withdrawal.partial_withdrawal = PartialWithdrawalTable(
        table_id="w", base_annual_rate=0.05, rates_by_duration={2: 0.15}
    )
    return config.model_copy(update=overrides)


def _portfolio():
    return [
        policy("NB-M", issue_age=60, surrender_charge_schedule_id="ATHENE_MYG_5"),
        policy(
            "IF-F-ROP",
            issue_date=date(2023, 7, 1),
            issue_age=67,
            sex="F",
            account_value=106_000.0,
            single_premium=110_000.0,
            guaranteed_rate=0.045,
            death_benefit_basis="ROP",
            surrender_charge_schedule_id="ATHENE_MYG_7_CA",
            guarantee_period_years=7,
        ),
        policy("NB-U", issue_age=85, sex="U", guaranteed_rate=0.02, guarantee_period_years=3),
        policy(
            "MATURED",
            issue_date=date(2019, 1, 1),
            guarantee_period_years=5,
            account_value=80_000.0,
        ),
    ]


def _reference(p, config: ProjectionBasisConfig, n_periods: int) -> dict[str, list[float]]:
    """Scalar month-by-month reference projection (independent of gaspatchio)."""
    m = config.mortality
    base = _MORT.get(m.base_table_id_by_sex[p.sex])
    g2 = _MORT.get(m.improvement_table_id_by_sex[p.sex])
    try:
        schedule = _SC.get(p.surrender_charge_schedule_id)
    except ValueError:
        schedule = None
    dur0 = (VAL_DATE.year - p.issue_date.year) * 12 + VAL_DATE.month - p.issue_date.month
    i = (1 + p.guaranteed_rate) ** (1 / 12) - 1
    av, in_force, matured = p.account_value, 1.0, False
    out: dict[str, list[float]] = {c: [] for c in (*CASH_FLOW_COLUMNS, "lives_in_force")}
    for t in range(n_periods):
        if matured:
            for values in out.values():
                values.append(0.0)
            continue
        start = VAL_DATE + relativedelta(months=t)
        end = VAL_DATE + relativedelta(months=t + 1)
        duration = dur0 + t
        year = duration // 12 + 1
        age = p.issue_age + duration // 12
        ys_g2 = max((start - m.g2_base_date).days / 365.25, 0.0)
        ys_issue = max((start - p.issue_date).days / 365.25, 0.0)
        qx = (
            base.rate_at_age(age)
            * m.mortality_multiplier
            * (1 - g2.rate_at_age(age) * m.g2_scale_multiplier) ** ys_g2
            * (1 - m.flat_improvement_rate) ** ys_issue
        )
        q = 1 - (1 - min(max(qx, 0.0), 1.0)) ** (1 / 12)
        lapse = config.lapse_config.rate_at_duration(year) if config.lapse_config.is_active else 0.0
        l_m = 1 - (1 - lapse) ** (1 / 12)
        w_a = config.withdrawal.partial_withdrawal.rate_at_duration(year)
        w = p.free_withdrawal_pct * (1 - (1 - w_a) ** (1 / 12)) if config.withdrawal.is_active else 0.0
        sc = schedule.charge_at_year(year) if schedule else 0.0

        mid = av * (1 + i)
        db = max(p.single_premium, mid) if p.death_benefit_basis == "ROP" else mid
        survivors = in_force * max(1 - q - l_m, 0.0)
        out["account_value_bop"].append(in_force * av)
        out["interest_credited"].append(in_force * av * i)
        out["death_benefits"].append(in_force * q * db)
        out["surrender_benefits"].append(in_force * l_m * mid * (1 - sc))
        out["surrender_charge"].append(in_force * l_m * mid * sc)
        out["mva_adjustment"].append(0.0)
        out["partial_withdrawals"].append(survivors * mid * w)
        av = mid * (1 - w)
        if end >= p.guarantee_end_date:
            out["maturity_benefits"].append(survivors * av)
            out["lives_in_force"].append(0.0)
            out["account_value_eop"].append(0.0)
            matured = True
        else:
            out["maturity_benefits"].append(0.0)
            out["lives_in_force"].append(survivors)
            out["account_value_eop"].append(survivors * av)
        in_force = survivors
    return out


@pytest.fixture(scope="module")
def projection():
    return myga.project(
        _portfolio(), _config(), VAL_DATE, projection_horizon_years=HORIZON_YEARS, detail=True
    )


def _row(projection, policy_id: str) -> dict:
    frame = projection.frame
    return frame.filter(frame["policy_id"] == policy_id).to_dicts()[0]


def test_reconciles_to_scalar_reference(projection):
    config = _config()
    n = HORIZON_YEARS * 12
    for p in _portfolio():
        expected = _reference(p, config, n)
        actual = _row(projection, p.policy_id)
        for column, values in expected.items():
            np.testing.assert_allclose(
                actual[column], values, rtol=1e-12, atol=1e-8, err_msg=f"{p.policy_id}.{column}"
            )


def test_account_value_rollforward_balances(projection):
    """AV_bop + interest = death + surrender + charge + withdrawals + maturity + AV_eop."""
    for row in projection.frame.to_dicts():
        lhs = np.array(row["account_value_bop"]) + np.array(row["interest_credited"])
        rhs = sum(
            np.array(row[c])
            for c in (
                "surrender_benefits",
                "surrender_charge",
                "partial_withdrawals",
                "maturity_benefits",
                "account_value_eop",
            )
        )
        # ROP death benefit can exceed AV — balance the AV-funded part only.
        deaths_at_av = np.array(row["in_force_bop"]) * np.array(row["monthly_qx"]) * np.array(
            row["av_mid_pp"]
        )
        np.testing.assert_allclose(lhs, rhs + deaths_at_av, rtol=1e-10, atol=1e-7)


def test_grid_starts_at_valuation_date(projection):
    assert projection.grid.valuation_date == VAL_DATE
    assert projection.grid.n_periods == HORIZON_YEARS * 12
    assert projection.grid.period_end_dates[0] == date(2025, 2, 1)
    assert all(len(v) == HORIZON_YEARS * 12 for v in projection.frame["death_benefits"])


def test_monthly_crediting_compounds_to_guaranteed_rate():
    config = _config(lapse_config=LapseRateTable(table_id="none", base_annual_rate=0.0))
    config.withdrawal.is_active = False
    row = _row(myga.project([policy(guaranteed_rate=0.03)], config, VAL_DATE), "P1")
    # Per-policy AV after 12 months is exactly 3% higher (no withdrawals).
    growth = (row["account_value_eop"][11] / row["lives_in_force"][11]) / 100_000.0
    assert growth == pytest.approx(1.03, rel=1e-12)
    assert row["account_value_bop"][0] == pytest.approx(100_000.0)


def test_lapse_shock_lands_on_policy_year(projection):
    """Policy year = duration_months // 12 + 1; the year-3 shock covers months 24-35."""
    row = _row(projection, "NB-M")
    assert row["policy_year"][23] == 2 and row["annual_lapse_rate"][23] == pytest.approx(0.02)
    assert row["policy_year"][24] == 3 and row["annual_lapse_rate"][24] == pytest.approx(0.20)
    assert row["annual_lapse_rate"][35] == pytest.approx(0.20)
    assert row["annual_lapse_rate"][36] == pytest.approx(0.02)


def test_in_force_policy_uses_current_duration(projection):
    """Issued 2023-07-01, valued 2025-01-01: 18 months in, policy year 2."""
    row = _row(projection, "IF-F-ROP")
    assert row["policy_year"][0] == 2
    assert row["surrender_charge_rate"][0] == pytest.approx(0.073)  # MYG7-CA year 2
    assert row["attained_age"][0] == 68


def test_maturity_pays_out_and_terminates(projection):
    row = _row(projection, "NB-M")  # 5-year guarantee from valuation → period 59
    assert row["maturity_benefits"][59] > 0.0
    assert row["lives_in_force"][59] == 0.0
    assert row["account_value_eop"][59] == 0.0
    assert sum(row["maturity_benefits"]) == pytest.approx(row["maturity_benefits"][59])
    for column in OUTFLOW_COLUMNS:
        assert all(v == 0.0 for v in row[column][60:])


def test_already_matured_policy_pays_in_first_period(projection):
    row = _row(projection, "MATURED")
    assert row["maturity_benefits"][0] > 0.0
    assert sum(row["lives_in_force"]) == 0.0


def test_rop_death_benefit_floors_at_premium(projection):
    row = _row(projection, "IF-F-ROP")
    deaths = np.array(row["in_force_bop"]) * np.array(row["monthly_qx"])
    live = deaths > 0
    per_death = np.array(row["death_benefits"])[live] / deaths[live]
    assert (per_death >= 110_000.0 - 1e-6).all()


def test_surrender_charge_only_within_schedule(projection):
    row = _row(projection, "NB-M")  # ATHENE_MYG_5: charges in policy years 1-5
    assert row["surrender_charge"][0] == pytest.approx(
        row["surrender_benefits"][0] * 0.08 / 0.92, rel=1e-12
    )
    unknown = _row(projection, "NB-U")  # "NONE" schedule → no charges
    assert sum(unknown["surrender_charge"]) == 0.0


def test_basis_assumptions_drive_the_projection():
    """Mortality and lapse levers on the config block change the cash flows."""
    base = myga.project([policy()], _config(), VAL_DATE)
    heavier = _config()
    heavier.mortality.mortality_multiplier = 1.5
    loaded = myga.project([policy()], heavier, VAL_DATE)
    assert sum(loaded.total("death_benefits")) > sum(base.total("death_benefits"))

    no_lapse = _config(lapse_config=LapseRateTable(table_id="off", base_annual_rate=0.5, is_active=False))
    assert sum(myga.project([policy()], no_lapse, VAL_DATE).total("surrender_benefits")) == 0.0


def test_empty_portfolio():
    projection = myga.project([], _config(), VAL_DATE)
    assert projection.is_empty
    assert projection.total("death_benefits") == [0.0] * projection.grid.n_periods


def test_detail_columns_are_opt_in():
    lean = myga.project([policy()], _config(), VAL_DATE)
    assert "monthly_qx" not in lean.frame.columns
    assert set(CASH_FLOW_COLUMNS) <= set(lean.frame.columns)

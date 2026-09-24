"""Tests for the projection grid, model points, and gaspatchio tables."""

from datetime import date

import polars as pl
import pytest
from gaspatchio import ActuarialFrame

from actuarial_model.engine.grid import ProjectionGrid, grid_vector, months_between
from actuarial_model.engine.model_points import maturity_period, myga_model_points
from actuarial_model.engine.tables import policy_year_table
from tests.factories import VAL_DATE, policy


def test_grid_dates_do_not_drift_from_month_end():
    grid = ProjectionGrid(valuation_date=date(2025, 1, 31), n_periods=3)
    assert grid.period_start_dates == [date(2025, 1, 31), date(2025, 2, 28), date(2025, 3, 31)]
    assert grid.period_end_dates[-1] == date(2025, 4, 30)


def test_grid_payment_tenors():
    grid = ProjectionGrid.from_horizon(VAL_DATE, 1)
    assert grid.n_periods == 12
    assert grid.payment_tenors[-1] == pytest.approx(365 / 365.25)


def test_maturity_period():
    assert maturity_period(VAL_DATE, date(2030, 1, 1)) == 59
    assert maturity_period(VAL_DATE, date(2030, 1, 15)) == 60  # needs the next period end
    assert maturity_period(VAL_DATE, date(2020, 1, 1)) == 0  # already matured


def test_model_points_resolve_timing():
    mp = myga_model_points([policy(issue_date=date(2023, 7, 1))], VAL_DATE)
    row = mp.to_dicts()[0]
    assert row["duration_months_at_valuation"] == months_between(date(2023, 7, 1), VAL_DATE) == 18
    assert row["months_to_maturity"] == 42
    assert row["maturity_period"] == 41


def test_tables_with_different_data_coexist():
    """Content-addressed names: two lapse tables never supersede each other."""
    low = policy_year_table("lapse", {3: 0.2}, 0.01)
    high = policy_year_table("lapse", {3: 0.5}, 0.02)
    assert low.name != high.name

    af = ActuarialFrame(pl.DataFrame({"x": [1]}))
    af.policy_year = grid_vector([1, 2, 3, 4], pl.Int64())
    af.low = low.lookup(policy_year=af.policy_year)
    af.high = high.lookup(policy_year=af.policy_year)
    row = af.collect().to_dicts()[0]
    assert row["low"] == pytest.approx([0.01, 0.01, 0.2, 0.01])
    assert row["high"] == pytest.approx([0.02, 0.02, 0.5, 0.02])


def test_identical_tables_share_a_name():
    assert policy_year_table("lapse", {3: 0.2}, 0.01).name == policy_year_table(
        "lapse", {3: 0.2}, 0.01
    ).name


def test_no_overrides_means_scalar_default():
    assert policy_year_table("lapse", {}, 0.01) is None

"""Tests for the discount-curve module."""

import itertools
from datetime import date

import pytest

from actuarial_model.assumptions.enums import CurveInterpolation, RiskFreeCurve
from actuarial_model.core.discount import (
    CurvePoint,
    DiscountCurve,
    DiscountInput,
    build_curve,
    calculate,
)

VAL_DATE = date(2025, 1, 1)


def _input(
    points: list[tuple[float, float]],
    interpolation: CurveInterpolation = CurveInterpolation.LINEAR,
) -> DiscountInput:
    return DiscountInput(
        valuation_date=VAL_DATE,
        curve=RiskFreeCurve.US_TREASURY,
        interpolation=interpolation,
        curve_points=[CurvePoint(tenor_years=t, rate=r) for t, r in points],
    )


class TestBuildCurve:
    def test_requires_curve_points(self):
        with pytest.raises(ValueError, match="curve_points"):
            build_curve(_input([]))

    def test_sorts_unsorted_points(self):
        curve = build_curve(_input([(10.0, 0.05), (1.0, 0.03), (5.0, 0.04)]))
        assert curve.tenors_years == [1.0, 5.0, 10.0]
        assert curve.zero_rates == [0.03, 0.04, 0.05]

    def test_rejects_duplicate_tenors(self):
        with pytest.raises(ValueError, match="duplicates"):
            build_curve(_input([(1.0, 0.03), (1.0, 0.04)]))


class TestZeroRate:
    def test_exact_node(self):
        curve = build_curve(_input([(1.0, 0.03), (5.0, 0.04)]))
        assert curve.zero_rate(1.0) == pytest.approx(0.03)
        assert curve.zero_rate(5.0) == pytest.approx(0.04)

    def test_linear_midpoint(self):
        curve = build_curve(_input([(1.0, 0.03), (5.0, 0.05)]))
        assert curve.zero_rate(3.0) == pytest.approx(0.04)

    def test_flat_extrapolation_beyond_ends(self):
        curve = build_curve(_input([(1.0, 0.03), (5.0, 0.05)]))
        assert curve.zero_rate(0.25) == pytest.approx(0.03)
        assert curve.zero_rate(30.0) == pytest.approx(0.05)

    def test_single_point_curve_is_flat(self):
        curve = build_curve(_input([(5.0, 0.04)]))
        assert curve.zero_rate(1.0) == pytest.approx(0.04)
        assert curve.zero_rate(20.0) == pytest.approx(0.04)

    def test_cubic_spline_hits_nodes(self):
        curve = build_curve(
            _input(
                [(1.0, 0.03), (2.0, 0.035), (5.0, 0.04), (10.0, 0.045)],
                interpolation=CurveInterpolation.CUBIC_SPLINE,
            )
        )
        assert curve.zero_rate(2.0) == pytest.approx(0.035)
        # Between nodes the spline stays within a sane band
        assert 0.03 < curve.zero_rate(3.0) < 0.045


class TestDiscountFactor:
    def test_formula(self):
        curve = build_curve(_input([(1.0, 0.04), (10.0, 0.04)]))
        assert curve.discount_factor(1.0) == pytest.approx(1.0 / 1.04)
        assert curve.discount_factor(2.0) == pytest.approx(1.04**-2)

    def test_zero_and_negative_tenor_is_one(self):
        curve = build_curve(_input([(1.0, 0.04)]))
        assert curve.discount_factor(0.0) == 1.0
        assert curve.discount_factor(-1.0) == 1.0

    def test_monotone_decreasing_for_positive_rates(self):
        curve = build_curve(_input([(1.0, 0.03), (10.0, 0.05)]))
        dfs = [curve.discount_factor(t) for t in (1, 2, 5, 10, 20)]
        assert all(a > b for a, b in itertools.pairwise(dfs))

    def test_discount_factor_for_date(self):
        curve = build_curve(_input([(1.0, 0.04), (10.0, 0.04)]))
        one_year_out = date(2026, 1, 1)
        df = curve.discount_factor_for_date(one_year_out)
        assert df == pytest.approx(1.0 / 1.04, rel=1e-3)

    def test_date_on_valuation_date_is_one(self):
        curve = build_curve(_input([(1.0, 0.04)]))
        assert curve.discount_factor_for_date(VAL_DATE) == 1.0


class TestCalculate:
    def test_monthly_grid(self):
        output = calculate(_input([(1.0, 0.03), (5.0, 0.04)]))
        assert len(output.tenors_years) == 60
        assert output.tenors_years[0] == pytest.approx(1 / 12)
        assert output.tenors_years[-1] == pytest.approx(5.0)
        assert len(output.discount_factors) == 60

    def test_grid_dfs_below_one(self):
        output = calculate(_input([(1.0, 0.03), (5.0, 0.04)]))
        assert all(0.0 < df < 1.0 for df in output.discount_factors)


class TestDiscountCurveValidation:
    def test_unsorted_tenors_rejected(self):
        with pytest.raises(ValueError, match="sorted"):
            DiscountCurve(
                valuation_date=VAL_DATE,
                tenors_years=[5.0, 1.0],
                zero_rates=[0.04, 0.03],
            )

    def test_length_mismatch_rejected(self):
        with pytest.raises(ValueError, match="same length"):
            DiscountCurve(
                valuation_date=VAL_DATE,
                tenors_years=[1.0, 5.0],
                zero_rates=[0.03],
            )

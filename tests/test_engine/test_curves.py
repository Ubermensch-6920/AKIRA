"""Tests for gaspatchio-backed curves and discount factors."""

import pytest

from actuarial_model.assumptions.enums import CurveInterpolation
from actuarial_model.engine.curves import CurvePoint, build_curve, discount_factors


def _points(*pairs: tuple[float, float]) -> list[CurvePoint]:
    return [CurvePoint(tenor_years=t, rate=r) for t, r in pairs]


def test_requires_curve_points():
    with pytest.raises(ValueError, match="curve_points"):
        build_curve([])


def test_rejects_duplicate_tenors():
    with pytest.raises(ValueError, match="duplicates"):
        build_curve(_points((1.0, 0.03), (1.0, 0.04)))


def test_sorts_unsorted_points():
    curve = build_curve(_points((30.0, 0.05), (1.0, 0.04)))
    assert curve.spot_rate(1.0) == pytest.approx(0.04)


def test_annual_compounding_formula():
    curve = build_curve(_points((1.0, 0.04), (30.0, 0.04)))
    assert discount_factors(curve, [2.5]) == [pytest.approx(1.04**-2.5)]


def test_linear_interpolation_between_knots():
    curve = build_curve(_points((1.0, 0.04), (30.0, 0.05)))
    expected_rate = 0.04 + (15.5 - 1.0) / 29.0 * 0.01
    assert discount_factors(curve, [15.5])[0] == pytest.approx((1 + expected_rate) ** -15.5)


def test_flat_extrapolation_beyond_both_ends():
    curve = build_curve(_points((1.0, 0.04), (30.0, 0.05)))
    short, long = discount_factors(curve, [0.5, 40.0])
    assert short == pytest.approx(1.04**-0.5)
    assert long == pytest.approx(1.05**-40.0)


def test_single_point_curve_is_flat():
    curve = build_curve(_points((5.0, 0.03)))
    assert discount_factors(curve, [1.0, 7.0]) == [
        pytest.approx(1.03**-1.0),
        pytest.approx(1.03**-7.0),
    ]


def test_zero_and_negative_tenors_discount_to_one():
    curve = build_curve(_points((1.0, 0.04), (30.0, 0.04)))
    assert discount_factors(curve, [0.0, -1.0]) == [1.0, 1.0]


def test_shift_and_floor():
    curve = build_curve(_points((1.0, 0.01), (30.0, 0.03)), shift=-0.02, floor=0.0)
    assert curve.spot_rate(1.0) == pytest.approx(0.0)
    assert curve.spot_rate(30.0) == pytest.approx(0.01)


@pytest.mark.parametrize("method", list(CurveInterpolation))
def test_every_interpolation_hits_knots(method: CurveInterpolation):
    curve = build_curve(_points((1.0, 0.04), (5.0, 0.03), (30.0, 0.05)), interpolation=method)
    for tenor, rate in ((1.0, 0.04), (5.0, 0.03), (30.0, 0.05)):
        assert discount_factors(curve, [tenor])[0] == pytest.approx((1 + rate) ** -tenor)

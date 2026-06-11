"""Smoke tests: every core / projection module raises NotImplementedError."""

import pytest

from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.core import aggregation, discount, seriatim
from actuarial_model.core.projections import fia, myga, spia, ulsg, va


def test_seriatim_empty_run(sample_assumption_set: AssumptionSet) -> None:
    """Seriatim is implemented — an empty policy list returns empty cash flows."""
    output = seriatim.calculate(
        seriatim.SeriatimInput(assumption_set=sample_assumption_set, policies=[])
    )
    assert output.cash_flows is not None
    assert output.cash_flows.policies == []


def test_aggregation_stub() -> None:
    with pytest.raises(NotImplementedError):
        aggregation.calculate(aggregation.AggregationInput(seriatim_results=[]))


def test_discount_requires_curve_points(sample_assumption_set: AssumptionSet) -> None:
    """Discount is implemented — calling it without curve points is a usage error."""
    cfg = sample_assumption_set.bel
    with pytest.raises(ValueError, match="curve_points"):
        discount.calculate(
            discount.DiscountInput(
                valuation_date=__import__("datetime").date(2025, 1, 1),
                curve=cfg.risk_free_curve,
                interpolation=cfg.curve_interpolation,
            )
        )


def test_myga_calculate_returns_output(sample_assumption_set: AssumptionSet) -> None:
    """MYGA engine is implemented — calculate() should succeed with an empty policy list."""
    output = myga.calculate(
        myga.MygaProjectionInput(assumption_set=sample_assumption_set, policies=[])
    )
    assert output.cash_flows is not None
    assert output.cash_flows.policies == []


@pytest.mark.parametrize(
    "module, input_cls",
    [
        (fia, fia.FiaProjectionInput),
        (spia, spia.SpiaProjectionInput),
        (va, va.VaProjectionInput),
        (ulsg, ulsg.UlsgProjectionInput),
    ],
)
def test_projection_stubs(
    module, input_cls, sample_assumption_set: AssumptionSet
) -> None:
    with pytest.raises(NotImplementedError):
        module.calculate(input_cls(assumption_set=sample_assumption_set, policies=[]))

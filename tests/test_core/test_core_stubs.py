"""Smoke tests: every core / projection module raises NotImplementedError."""

import pytest

from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.core import aggregation, discount, seriatim
from actuarial_model.core.projections import fia, myga, spia, ulsg, va


def test_seriatim_dispatch_stub(sample_assumption_set: AssumptionSet) -> None:
    with pytest.raises(NotImplementedError):
        seriatim.calculate(
            seriatim.SeriatimInput(assumption_set=sample_assumption_set, policies=[])
        )


def test_aggregation_stub() -> None:
    with pytest.raises(NotImplementedError):
        aggregation.calculate(aggregation.AggregationInput(seriatim_results=[]))


def test_discount_stub(sample_assumption_set: AssumptionSet) -> None:
    cfg = sample_assumption_set.bel
    with pytest.raises(NotImplementedError):
        discount.calculate(
            discount.DiscountInput(
                valuation_date=__import__("datetime").date(2025, 1, 1),
                curve=cfg.risk_free_curve,
                interpolation=cfg.curve_interpolation,
            )
        )


@pytest.mark.parametrize(
    "module, input_cls",
    [
        (myga, myga.MygaProjectionInput),
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

"""Smoke tests: capital frameworks raise NotImplementedError in Phase 1."""

import pytest

from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.capital import ecr, rbc, stochastic


@pytest.mark.parametrize(
    "module, input_cls",
    [
        (rbc, rbc.RbcInput),
        (ecr, ecr.EcrInput),
        (stochastic, stochastic.StochasticCapitalInput),
    ],
)
def test_capital_stubs(
    module, input_cls, sample_assumption_set: AssumptionSet
) -> None:
    with pytest.raises(NotImplementedError):
        module.calculate(input_cls(assumption_set=sample_assumption_set))

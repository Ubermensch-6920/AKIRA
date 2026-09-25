"""Smoke tests: capital stubs raise NotImplementedError in Phase 1."""

import pytest

from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.bases.ebs import ecr
from actuarial_model.bases.stat import rbc
from actuarial_model.capital import stochastic


def test_rbc_empty_run(sample_assumption_set: AssumptionSet) -> None:
    """RBC is implemented — no reserves and no assets yield zero capital."""
    output = rbc.calculate(rbc.RbcInput(assumption_set=sample_assumption_set))
    assert output.capital_result.capital_amount == 0.0


@pytest.mark.parametrize(
    "module, input_cls",
    [
        (ecr, ecr.EcrInput),
        (stochastic, stochastic.StochasticCapitalInput),
    ],
)
def test_capital_stubs(
    module, input_cls, sample_assumption_set: AssumptionSet
) -> None:
    with pytest.raises(NotImplementedError):
        module.calculate(input_cls(assumption_set=sample_assumption_set))

"""Smoke tests: every reserve framework module raises NotImplementedError."""

import pytest

from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.standards import bel, ebs, fas157, ldti, stat_carvm, stat_vm22


def test_bel_requires_cash_flows(sample_assumption_set: AssumptionSet) -> None:
    """BEL is implemented — calling it without cash flows is a usage error."""
    with pytest.raises(ValueError, match="gross_cash_flows"):
        bel.calculate(bel.BelInput(assumption_set=sample_assumption_set))


@pytest.mark.parametrize(
    "module, input_cls",
    [
        (stat_carvm, stat_carvm.StatCarvmInput),
        (stat_vm22, stat_vm22.StatVm22Input),
        (ldti, ldti.LdtiInput),
        (fas157, fas157.Fas157Input),
        (ebs, ebs.EbsInput),
    ],
)
def test_standards_stubs(
    module, input_cls, sample_assumption_set: AssumptionSet
) -> None:
    with pytest.raises(NotImplementedError):
        module.calculate(input_cls(assumption_set=sample_assumption_set))

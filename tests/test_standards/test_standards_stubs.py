"""Smoke tests: every reserve framework module guards its required inputs."""

import pytest

from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.standards import bel, ebs, fas157, ldti, stat_carvm, stat_vm22


def test_bel_requires_cash_flows(sample_assumption_set: AssumptionSet) -> None:
    """BEL is implemented — calling it without cash flows is a usage error."""
    with pytest.raises(ValueError, match="gross_cash_flows"):
        bel.calculate(bel.BelInput(assumption_set=sample_assumption_set))


def test_stat_carvm_empty_run(sample_assumption_set: AssumptionSet) -> None:
    """CARVM is implemented — an empty policy list yields a zero reserve."""
    output = stat_carvm.calculate(
        stat_carvm.StatCarvmInput(assumption_set=sample_assumption_set)
    )
    assert output.reserve_result.gross_reserve == 0.0


@pytest.mark.parametrize(
    "module, input_cls",
    [
        (stat_vm22, stat_vm22.StatVm22Input),
        (ldti, ldti.LdtiInput),
        (fas157, fas157.Fas157Input),
        (ebs, ebs.EbsInput),
    ],
)
def test_frameworks_require_cash_flows(
    module, input_cls, sample_assumption_set: AssumptionSet
) -> None:
    """Every framework is implemented — missing cash flows is a usage error."""
    with pytest.raises(ValueError, match="gross_cash_flows"):
        module.calculate(input_cls(assumption_set=sample_assumption_set))

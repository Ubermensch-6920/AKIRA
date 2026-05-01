"""Smoke tests for assumption-set defaults and validators."""

import pytest

from actuarial_model.assumptions.enums import (
    CTELevel,
    StatCarvmBasis,
    Vm22Component,
)
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.assumptions.validators import validate_assumption_set


def test_default_levers(sample_assumption_set: AssumptionSet) -> None:
    assert sample_assumption_set.stat_carvm.carvm_basis is StatCarvmBasis.AG35
    assert sample_assumption_set.stat_vm22.cte_level is CTELevel.CTE70
    assert sample_assumption_set.stat_vm22.reserve_component is Vm22Component.DR_SR_MAX


def test_validator_stub_raises(sample_assumption_set: AssumptionSet) -> None:
    with pytest.raises(NotImplementedError):
        validate_assumption_set(sample_assumption_set)

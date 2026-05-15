"""Smoke tests for assumption-set defaults and validators."""

import pytest

from actuarial_model.assumptions.enums import (
    CTELevel,
    StatCarvmBasis,
    Vm22Component,
)
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.assumptions.validators import ValidationIssue, validate_assumption_set


def test_default_levers(sample_assumption_set: AssumptionSet) -> None:
    assert sample_assumption_set.stat_carvm.carvm_basis is StatCarvmBasis.AG35
    assert sample_assumption_set.stat_vm22.cte_level is CTELevel.CTE70
    assert sample_assumption_set.stat_vm22.reserve_component is Vm22Component.DR_SR_MAX


def test_validator_returns_list(sample_assumption_set: AssumptionSet) -> None:
    issues = validate_assumption_set(sample_assumption_set)
    assert isinstance(issues, list)
    assert all(isinstance(i, ValidationIssue) for i in issues)


def test_validator_flags_bad_fas157_coc(sample_assumption_set: AssumptionSet) -> None:
    sample_assumption_set.fas157.cost_of_capital_rate = 0.99
    issues = validate_assumption_set(sample_assumption_set)
    codes = [i.code for i in issues]
    assert "FAS157_COC_RANGE" in codes


def test_validator_flags_bad_ebs_coc(sample_assumption_set: AssumptionSet) -> None:
    sample_assumption_set.ebs.cost_of_capital_rate = 0.0
    issues = validate_assumption_set(sample_assumption_set)
    codes = [i.code for i in issues]
    assert "EBS_COC_RANGE" in codes


def test_validator_flags_bad_ldti_npr_cap(sample_assumption_set: AssumptionSet) -> None:
    sample_assumption_set.ldti.net_premium_ratio_cap = 0.0
    issues = validate_assumption_set(sample_assumption_set)
    errors = [i for i in issues if i.severity == "error"]
    assert any(i.code == "LDTI_NPR_CAP_RANGE" for i in errors)


def test_validator_clean_defaults(sample_assumption_set: AssumptionSet) -> None:
    issues = validate_assumption_set(sample_assumption_set)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == [], f"Default assumption set should produce no errors; got: {errors}"

"""Tests for the seriatim dispatcher."""

from datetime import date

import pytest

from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.core.seriatim import SeriatimInput, calculate
from actuarial_model.models.policy import FiaPolicyState, MygaPolicyState


def _myga_policy(policy_id: str = "POL-0001") -> MygaPolicyState:
    return MygaPolicyState(
        policy_id=policy_id,
        issue_date=date(2024, 1, 1),
        issue_age=60,
        sex="M",
        issue_state="NY",
        legal_entity="ENT-A",
        segment="MYGA-RETAIL",
        cohort_id="2024Q1",
        valuation_date=date(2024, 1, 1),
        single_premium=100_000.0,
        account_value=100_000.0,
        guaranteed_rate=0.03,
        guarantee_period_years=5,
        guarantee_end_date=date(2029, 1, 1),
        surrender_charge_schedule_id="ATHENE_MYG_5",
    )


def test_routes_myga_policies(sample_assumption_set: AssumptionSet):
    output = calculate(
        SeriatimInput(
            assumption_set=sample_assumption_set,
            policies=[_myga_policy("A"), _myga_policy("B")],
            valuation_date=date(2024, 1, 1),
        )
    )
    assert output.cash_flows is not None
    assert {p.policy_id for p in output.cash_flows.policies} == {"A", "B"}
    assert all(p.records for p in output.cash_flows.policies)


def test_unsupported_product_raises(sample_assumption_set: AssumptionSet):
    fia = FiaPolicyState(
        policy_id="FIA-1",
        issue_date=date(2024, 1, 1),
        issue_age=60,
        sex="F",
        issue_state="TX",
        legal_entity="ENT-A",
        segment="FIA-RETAIL",
        cohort_id="2024Q1",
        valuation_date=date(2024, 1, 1),
    )
    with pytest.raises(NotImplementedError, match="FIA"):
        calculate(
            SeriatimInput(
                assumption_set=sample_assumption_set,
                policies=[_myga_policy(), fia],
            )
        )


def test_empty_policy_list(sample_assumption_set: AssumptionSet):
    output = calculate(
        SeriatimInput(
            assumption_set=sample_assumption_set,
            policies=[],
            valuation_date=date(2024, 1, 1),
        )
    )
    assert output.cash_flows is not None
    assert output.cash_flows.policies == []
    assert output.cash_flows.valuation_date == date(2024, 1, 1)

"""Tests for the reinsurance application (policy → treaty routing) step."""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import ReinsuranceTreatyType
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.models.cash_flows import (
    GrossCashFlows,
    MygaCashFlowRecord,
    PolicyCashFlows,
)
from actuarial_model.models.policy import MygaPolicyState
from actuarial_model.models.reinsurance import ReinsuranceTreaty
from actuarial_model.reinsurance.application import (
    ReinsuranceApplicationInput,
    calculate,
)

VAL_DATE = date(2025, 1, 1)


def _record(policy_id: str) -> MygaCashFlowRecord:
    return MygaCashFlowRecord(
        policy_id=policy_id,
        period=1,
        period_start_date=VAL_DATE,
        period_end_date=date(2025, 2, 1),
        account_value_bop=100_000.0,
        interest_credited=0.0,
        partial_withdrawals=0.0,
        surrender_charge=0.0,
        mva_adjustment=0.0,
        surrender_benefits=1_000.0,
        death_benefits=500.0,
        maturity_benefits=0.0,
        account_value_eop=98_500.0,
        lives_in_force=1.0,
    )


def _gross(policy_ids: list[str]) -> GrossCashFlows:
    return GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[
            PolicyCashFlows(policy_id=pid, records=[_record(pid)]) for pid in policy_ids
        ],
    )


def _policy(policy_id: str, treaty_id: str | None) -> MygaPolicyState:
    return MygaPolicyState(
        policy_id=policy_id,
        issue_date=date(2024, 1, 1),
        issue_age=60,
        sex="M",
        issue_state="NY",
        legal_entity="ENT-A",
        segment="MYGA-RETAIL",
        cohort_id="2024Q1",
        valuation_date=VAL_DATE,
        single_premium=100_000.0,
        account_value=100_000.0,
        guaranteed_rate=0.03,
        guarantee_period_years=5,
        guarantee_end_date=date(2029, 1, 1),
        surrender_charge_schedule_id="NONE",
        reinsurance_treaty_id=treaty_id,
    )


def test_mixed_reinsured_and_retained(
    sample_assumption_set: AssumptionSet, sample_treaty: ReinsuranceTreaty
):
    """P1 is 50% ceded; P2 has no treaty and stays fully retained."""
    output = calculate(
        ReinsuranceApplicationInput(
            assumption_set=sample_assumption_set,
            treaties=[sample_treaty],
            gross_cash_flows=_gross(["P1", "P2"]),
            policies=[_policy("P1", sample_treaty.treaty_id), _policy("P2", None)],
        )
    )

    ceded_ids = [p.policy_id for p in output.ceded_cash_flows.policies]
    net_ids = [p.policy_id for p in output.net_cash_flows.policies]
    assert ceded_ids == ["P1"]
    assert net_ids == ["P1", "P2"]

    net_p1 = output.net_cash_flows.policies[0].records[0]
    net_p2 = output.net_cash_flows.policies[1].records[0]
    assert net_p1.surrender_benefits == pytest.approx(500.0)  # retained half
    assert net_p2.surrender_benefits == pytest.approx(1_000.0)  # untouched gross


def test_no_policy_mapping_means_all_retained(
    sample_assumption_set: AssumptionSet, sample_treaty: ReinsuranceTreaty
):
    gross = _gross(["P1"])
    output = calculate(
        ReinsuranceApplicationInput(
            assumption_set=sample_assumption_set,
            treaties=[sample_treaty],
            gross_cash_flows=gross,
        )
    )
    assert output.ceded_cash_flows.policies == []
    assert output.net_cash_flows == gross


def test_unknown_treaty_id_raises(
    sample_assumption_set: AssumptionSet, sample_treaty: ReinsuranceTreaty
):
    with pytest.raises(ValueError, match="TRT-MISSING"):
        calculate(
            ReinsuranceApplicationInput(
                assumption_set=sample_assumption_set,
                treaties=[sample_treaty],
                gross_cash_flows=_gross(["P1"]),
                policies=[_policy("P1", "TRT-MISSING")],
            )
        )


def test_phase2_treaty_type_raises(
    sample_assumption_set: AssumptionSet, sample_treaty: ReinsuranceTreaty
):
    modco = sample_treaty.model_copy(
        update={"treaty_type": ReinsuranceTreatyType.MODCO}
    )
    with pytest.raises(NotImplementedError, match="MODCO"):
        calculate(
            ReinsuranceApplicationInput(
                assumption_set=sample_assumption_set,
                treaties=[modco],
                gross_cash_flows=_gross(["P1"]),
                policies=[_policy("P1", modco.treaty_id)],
            )
        )

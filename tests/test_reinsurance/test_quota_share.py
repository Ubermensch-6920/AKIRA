"""Tests for the quota-share reinsurance engine."""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import ReinsuranceTreatyType
from actuarial_model.models.cash_flows import (
    GrossCashFlows,
    MygaCashFlowRecord,
    PolicyCashFlows,
)
from actuarial_model.models.reinsurance import ReinsuranceTreaty
from actuarial_model.reinsurance.quota_share import QuotaShareInput, calculate

VAL_DATE = date(2025, 1, 1)


def _record(policy_id: str = "P1", period: int = 1) -> MygaCashFlowRecord:
    return MygaCashFlowRecord(
        policy_id=policy_id,
        period=period,
        period_start_date=VAL_DATE,
        period_end_date=date(2025, 2, 1),
        account_value_bop=100_000.0,
        interest_credited=250.0,
        partial_withdrawals=400.0,
        surrender_charge=90.0,
        mva_adjustment=0.0,
        surrender_benefits=1_000.0,
        death_benefits=300.0,
        maturity_benefits=0.0,
        account_value_eop=98_460.0,
        lives_in_force=0.98,
    )


def _gross(policy_ids: list[str]) -> GrossCashFlows:
    return GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[
            PolicyCashFlows(policy_id=pid, records=[_record(pid)]) for pid in policy_ids
        ],
    )


def test_fifty_percent_split(sample_treaty: ReinsuranceTreaty):
    output = calculate(
        QuotaShareInput(treaty=sample_treaty, gross_cash_flows=_gross(["P1"]))
    )
    ceded = output.ceded_cash_flows.policies[0].records[0]
    retained = output.retained_cash_flows.policies[0].records[0]

    assert ceded.surrender_benefits == pytest.approx(500.0)
    assert retained.surrender_benefits == pytest.approx(500.0)
    assert ceded.death_benefits == pytest.approx(150.0)
    assert ceded.account_value_bop == pytest.approx(50_000.0)


def test_ceded_plus_retained_equals_gross(sample_treaty: ReinsuranceTreaty):
    treaty = sample_treaty.model_copy(update={"quota_share_pct": 0.35})
    gross = _gross(["P1", "P2"])
    output = calculate(QuotaShareInput(treaty=treaty, gross_cash_flows=gross))

    monetary = [
        "account_value_bop",
        "interest_credited",
        "partial_withdrawals",
        "surrender_charge",
        "surrender_benefits",
        "death_benefits",
        "maturity_benefits",
        "account_value_eop",
    ]
    for g_cf, c_cf, r_cf in zip(
        gross.policies,
        output.ceded_cash_flows.policies,
        output.retained_cash_flows.policies,
        strict=True,
    ):
        for g, c, r in zip(g_cf.records, c_cf.records, r_cf.records, strict=True):
            for field in monetary:
                assert getattr(c, field) + getattr(r, field) == pytest.approx(
                    getattr(g, field)
                ), field


def test_lives_in_force_not_ceded(sample_treaty: ReinsuranceTreaty):
    """Policy counts are shared risk, not split lives."""
    output = calculate(
        QuotaShareInput(treaty=sample_treaty, gross_cash_flows=_gross(["P1"]))
    )
    assert output.ceded_cash_flows.policies[0].records[0].lives_in_force == 0.98
    assert output.retained_cash_flows.policies[0].records[0].lives_in_force == 0.98


def test_rejects_non_quota_share_treaty(sample_treaty: ReinsuranceTreaty):
    treaty = sample_treaty.model_copy(
        update={"treaty_type": ReinsuranceTreatyType.COINSURANCE}
    )
    with pytest.raises(ValueError, match="QUOTA_SHARE"):
        calculate(QuotaShareInput(treaty=treaty, gross_cash_flows=_gross(["P1"])))


def test_rejects_missing_pct(sample_treaty: ReinsuranceTreaty):
    treaty = sample_treaty.model_copy(update={"quota_share_pct": None})
    with pytest.raises(ValueError, match="quota_share_pct"):
        calculate(QuotaShareInput(treaty=treaty, gross_cash_flows=_gross(["P1"])))


def test_rejects_out_of_range_pct(sample_treaty: ReinsuranceTreaty):
    treaty = sample_treaty.model_copy(update={"quota_share_pct": 1.25})
    with pytest.raises(ValueError, match="must be in"):
        calculate(QuotaShareInput(treaty=treaty, gross_cash_flows=_gross(["P1"])))

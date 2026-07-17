"""Tests for the Phase 2 treaty engines: coinsurance, ModCo, FWH, YRT, XL."""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import (
    CollateralType,
    ReinsuranceTreatyType,
    ReinsurerAuthStatus,
    RiskTransferMethod,
)
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.models.cash_flows import (
    GrossCashFlows,
    MygaCashFlowRecord,
    PolicyCashFlows,
)
from actuarial_model.models.policy import MygaPolicyState
from actuarial_model.models.reinsurance import ReinsuranceTreaty
from actuarial_model.reinsurance import (
    application,
    coinsurance,
    excess_of_loss,
    funds_withheld,
    modco,
    yrt,
)

VAL_DATE = date(2025, 1, 1)


def _treaty(treaty_type: ReinsuranceTreatyType, **overrides) -> ReinsuranceTreaty:
    fields: dict = dict(
        treaty_id=f"TRT-{treaty_type.value}",
        treaty_name=f"Test {treaty_type.value}",
        counterparty="Test Re",
        counterparty_rating="A",
        auth_status=ReinsurerAuthStatus.AUTHORIZED,
        treaty_type=treaty_type,
        effective_date=date(2024, 1, 1),
        collateral_type=CollateralType.NONE,
        risk_transfer_method=RiskTransferMethod.REASONABLE_POSSIBILITY,
    )
    fields.update(overrides)
    return ReinsuranceTreaty(**fields)


def _record(
    policy_id: str,
    period: int = 1,
    *,
    death: float = 300.0,
    surrender: float = 1_000.0,
) -> MygaCashFlowRecord:
    start = date(2025, period, 1)
    end = date(2025, period + 1, 1)
    return MygaCashFlowRecord(
        policy_id=policy_id,
        period=period,
        period_start_date=start,
        period_end_date=end,
        account_value_bop=100_000.0,
        interest_credited=250.0,
        partial_withdrawals=400.0,
        surrender_charge=90.0,
        mva_adjustment=0.0,
        surrender_benefits=surrender,
        death_benefits=death,
        maturity_benefits=0.0,
        account_value_eop=98_460.0,
        lives_in_force=0.98,
    )


def _gross(policy_ids: list[str], **record_kwargs) -> GrossCashFlows:
    return GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[
            PolicyCashFlows(policy_id=pid, records=[_record(pid, **record_kwargs)])
            for pid in policy_ids
        ],
    )


def _policy(policy_id: str, treaty_id: str | None, basis: str = "ROAV") -> MygaPolicyState:
    return MygaPolicyState(
        policy_id=policy_id,
        issue_date=date(2024, 1, 1),
        issue_age=60,
        sex="M",
        issue_state="TX",
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
        death_benefit_basis=basis,
        reinsurance_treaty_id=treaty_id,
    )


# ── Coinsurance ───────────────────────────────────────────────────────────
def test_coinsurance_proportional_split_and_asset_transfer():
    treaty = _treaty(ReinsuranceTreatyType.COINSURANCE, coinsurance_pct=0.40)
    output = coinsurance.calculate(
        coinsurance.CoinsuranceInput(treaty=treaty, gross_cash_flows=_gross(["P1"]))
    )
    ceded = output.ceded_cash_flows.policies[0].records[0]
    retained = output.retained_cash_flows.policies[0].records[0]
    assert ceded.surrender_benefits == pytest.approx(400.0)
    assert retained.surrender_benefits == pytest.approx(600.0)
    assert ceded.death_benefits == pytest.approx(120.0)
    # Assets transferred: ceded share of first-period AV.
    assert output.initial_asset_transfer == pytest.approx(40_000.0)


def test_coinsurance_requires_pct():
    treaty = _treaty(ReinsuranceTreatyType.COINSURANCE)  # no coinsurance_pct
    with pytest.raises(ValueError, match="coinsurance_pct"):
        coinsurance.calculate(
            coinsurance.CoinsuranceInput(treaty=treaty, gross_cash_flows=_gross(["P1"]))
        )


# ── ModCo ─────────────────────────────────────────────────────────────────
def test_modco_restates_ceded_interest_at_modco_rate():
    treaty = _treaty(
        ReinsuranceTreatyType.MODCO, coinsurance_pct=0.50, modco_interest_rate=0.04
    )
    output = modco.calculate(
        modco.ModcoInput(treaty=treaty, gross_cash_flows=_gross(["P1"]))
    )
    ceded = output.ceded_cash_flows.policies[0].records[0]
    # Benefits still proportional…
    assert ceded.surrender_benefits == pytest.approx(500.0)
    # …but ceded interest is the ModCo credit on the ceded AV, not the
    # 50% share of gross crediting (125).
    year_fraction = 31 / 365.25
    expected = 50_000.0 * (1.04**year_fraction - 1.0)
    assert ceded.interest_credited == pytest.approx(expected, rel=1e-9)
    assert output.total_modco_interest == pytest.approx(expected, rel=1e-9)


def test_modco_requires_rate():
    treaty = _treaty(ReinsuranceTreatyType.MODCO, coinsurance_pct=0.50)
    with pytest.raises(ValueError, match="modco_interest_rate"):
        modco.calculate(modco.ModcoInput(treaty=treaty, gross_cash_flows=_gross(["P1"])))


# ── Funds withheld ────────────────────────────────────────────────────────
def test_fwh_tracks_account_balance():
    treaty = _treaty(
        ReinsuranceTreatyType.FUNDS_WITHHELD,
        coinsurance_pct=0.50,
        funds_withheld_rate=0.04,
    )
    output = funds_withheld.calculate(
        funds_withheld.FundsWithheldInput(treaty=treaty, gross_cash_flows=_gross(["P1"]))
    )
    ceded = output.ceded_cash_flows.policies[0].records[0]
    assert ceded.death_benefits == pytest.approx(150.0)  # proportional split intact

    # FW account: seed 50,000, accrete one month at 4%, pay ceded benefits
    # (150 death + 500 surrender + 200 withdrawals).
    year_fraction = 31 / 365.25
    fw_interest = 50_000.0 * (1.04**year_fraction - 1.0)
    expected_balance = 50_000.0 + fw_interest - (150.0 + 500.0 + 200.0)
    assert output.ending_fw_balance_by_policy["P1"] == pytest.approx(
        expected_balance, rel=1e-9
    )
    assert output.total_fw_interest == pytest.approx(fw_interest, rel=1e-9)


# ── YRT ───────────────────────────────────────────────────────────────────
def test_yrt_cedes_death_only_on_rop():
    treaty = _treaty(ReinsuranceTreatyType.YRT, quota_share_pct=0.80)
    gross = _gross(["ROP-1", "ROAV-1"])
    policies = [
        _policy("ROP-1", treaty.treaty_id, basis="ROP"),
        _policy("ROAV-1", treaty.treaty_id, basis="ROAV"),
    ]
    output = yrt.calculate(
        yrt.YrtInput(treaty=treaty, gross_cash_flows=gross, policies=policies)
    )
    by_id = {p.policy_id: p for p in output.ceded_cash_flows.policies}

    rop_ceded = by_id["ROP-1"].records[0]
    assert rop_ceded.death_benefits == pytest.approx(0.8 * 300.0)
    assert rop_ceded.surrender_benefits == 0.0  # mortality-only cover
    assert rop_ceded.account_value_bop == 0.0

    # ROAV: no net amount at risk, nothing cedes.
    assert by_id["ROAV-1"].records[0].death_benefits == 0.0

    retained_rop = {
        p.policy_id: p for p in output.retained_cash_flows.policies
    }["ROP-1"].records[0]
    assert retained_rop.death_benefits == pytest.approx(0.2 * 300.0)
    assert retained_rop.surrender_benefits == pytest.approx(1_000.0)  # untouched


# ── Excess of loss ────────────────────────────────────────────────────────
def test_xl_layers_aggregate_annual_claims():
    """Block claims 500 vs attachment 200, limit 200 → recovery 200 (40%),
    allocated pro-rata to each policy's deaths."""
    treaty = _treaty(
        ReinsuranceTreatyType.EXCESS_OF_LOSS, xl_attachment=200.0, xl_limit=200.0
    )
    gross = _gross(["P1", "P2"], death=250.0)  # 500 aggregate deaths in year 1
    output = excess_of_loss.calculate(
        excess_of_loss.ExcessOfLossInput(treaty=treaty, gross_cash_flows=gross)
    )
    assert output.recoveries_by_year == {1: pytest.approx(200.0)}
    for policy_cf in output.ceded_cash_flows.policies:
        assert policy_cf.records[0].death_benefits == pytest.approx(100.0)  # 40% of 250
        assert policy_cf.records[0].surrender_benefits == 0.0
    for policy_cf in output.retained_cash_flows.policies:
        assert policy_cf.records[0].death_benefits == pytest.approx(150.0)


def test_xl_below_attachment_cedes_nothing():
    treaty = _treaty(
        ReinsuranceTreatyType.EXCESS_OF_LOSS, xl_attachment=10_000.0, xl_limit=5_000.0
    )
    output = excess_of_loss.calculate(
        excess_of_loss.ExcessOfLossInput(
            treaty=treaty, gross_cash_flows=_gross(["P1"], death=250.0)
        )
    )
    assert output.recoveries_by_year == {}
    assert output.ceded_cash_flows.policies[0].records[0].death_benefits == 0.0


def test_xl_capped_at_limit():
    treaty = _treaty(
        ReinsuranceTreatyType.EXCESS_OF_LOSS, xl_attachment=100.0, xl_limit=50.0
    )
    output = excess_of_loss.calculate(
        excess_of_loss.ExcessOfLossInput(
            treaty=treaty, gross_cash_flows=_gross(["P1"], death=1_000.0)
        )
    )
    assert output.recoveries_by_year == {1: pytest.approx(50.0)}


# ── Application routing across treaty types ──────────────────────────────
def test_application_routes_all_types(sample_assumption_set: AssumptionSet):
    """A mixed block: coinsurance and ModCo groups plus an unreinsured
    policy route to the right engines and reassemble in order."""
    coins = _treaty(ReinsuranceTreatyType.COINSURANCE, coinsurance_pct=0.40)
    mod = _treaty(
        ReinsuranceTreatyType.MODCO, coinsurance_pct=0.50, modco_interest_rate=0.04
    )
    gross = _gross(["P1", "P2", "P3"])
    policies = [
        _policy("P1", coins.treaty_id),
        _policy("P2", mod.treaty_id),
        _policy("P3", None),
    ]
    output = application.calculate(
        application.ReinsuranceApplicationInput(
            assumption_set=sample_assumption_set,
            treaties=[coins, mod],
            gross_cash_flows=gross,
            policies=policies,
        )
    )
    assert [p.policy_id for p in output.ceded_cash_flows.policies] == ["P1", "P2"]
    assert [p.policy_id for p in output.net_cash_flows.policies] == ["P1", "P2", "P3"]

    ceded = {p.policy_id: p.records[0] for p in output.ceded_cash_flows.policies}
    assert ceded["P1"].surrender_benefits == pytest.approx(400.0)  # 40% coinsurance
    assert ceded["P2"].surrender_benefits == pytest.approx(500.0)  # 50% ModCo
    net = {p.policy_id: p.records[0] for p in output.net_cash_flows.policies}
    assert net["P3"].surrender_benefits == pytest.approx(1_000.0)  # untouched


def test_application_xl_attaches_on_group_aggregate(
    sample_assumption_set: AssumptionSet,
):
    """XL layer sees the treaty group's combined claims, not each policy:
    two policies at 250 each pierce a 400 attachment that neither would
    alone."""
    xl = _treaty(
        ReinsuranceTreatyType.EXCESS_OF_LOSS, xl_attachment=400.0, xl_limit=1_000.0
    )
    gross = _gross(["P1", "P2"], death=250.0)
    policies = [_policy("P1", xl.treaty_id), _policy("P2", xl.treaty_id)]
    output = application.calculate(
        application.ReinsuranceApplicationInput(
            assumption_set=sample_assumption_set,
            treaties=[xl],
            gross_cash_flows=gross,
            policies=policies,
        )
    )
    total_ceded_deaths = sum(
        r.death_benefits for p in output.ceded_cash_flows.policies for r in p.records
    )
    assert total_ceded_deaths == pytest.approx(100.0)  # 500 aggregate - 400 attachment

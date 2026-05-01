"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import date

import pytest

from actuarial_model.assumptions.enums import (
    CollateralType,
    ReinsuranceTreatyType,
    ReinsurerAuthStatus,
    RiskTransferMethod,
)
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.models.asset import AssetRecord
from actuarial_model.models.policy import MygaPolicyState
from actuarial_model.models.reinsurance import ReinsuranceTreaty


@pytest.fixture
def sample_assumption_set() -> AssumptionSet:
    """A default-configured assumption set."""
    return AssumptionSet(
        assumption_set_id="as-test-0001",
        version="0.1.0",
        description="Test fixture",
        created_by="pytest",
        created_date=date(2025, 1, 1),
    )


@pytest.fixture
def sample_policy() -> MygaPolicyState:
    """A representative MYGA policy."""
    return MygaPolicyState(
        policy_id="POL-0001",
        issue_date=date(2024, 1, 1),
        issue_age=60,
        sex="M",
        issue_state="NY",
        legal_entity="ENT-A",
        segment="MYGA-RETAIL",
        cohort_id="2024Q1",
        valuation_date=date(2025, 1, 1),
        single_premium=100_000.0,
        account_value=103_000.0,
        guaranteed_rate=0.03,
        guarantee_period_years=5,
        guarantee_end_date=date(2029, 1, 1),
        surrender_charge_schedule_id="SCHED-5YR",
    )


@pytest.fixture
def sample_asset() -> AssetRecord:
    """A representative corporate-bond asset."""
    return AssetRecord(
        asset_id="AST-0001",
        cusip="037833100",
        issuer="Sample Corp",
        sector="Industrial",
        asset_type="BOND",
        coupon_rate=0.045,
        maturity_date=date(2034, 6, 1),
        par_amount=1_000_000.0,
        book_value=998_000.0,
        amortized_cost=998_500.0,
        market_value=1_010_000.0,
        fair_value_level="LEVEL_2",
        unrealized_gl=11_500.0,
        oas_spread=125.0,
        credit_rating="A",
        naic_designation=2,
        modified_duration=8.5,
        convexity=0.85,
        spread_duration=8.6,
        gaap_classification="AFS",
        admitted_flag=True,
        bma_asset_class="CORP",
        market_value_ebs=1_005_000.0,
    )


@pytest.fixture
def sample_treaty() -> ReinsuranceTreaty:
    """A 50% quota-share reinsurance treaty."""
    return ReinsuranceTreaty(
        treaty_id="TRT-0001",
        treaty_name="Sample QS",
        counterparty="Sample Re",
        counterparty_rating="A+",
        auth_status=ReinsurerAuthStatus.AUTHORIZED,
        treaty_type=ReinsuranceTreatyType.QUOTA_SHARE,
        effective_date=date(2024, 1, 1),
        quota_share_pct=0.50,
        ceding_commission_pct=0.01,
        collateral_type=CollateralType.TRUST,
        collateral_amount=5_000_000.0,
        risk_transfer_method=RiskTransferMethod.REASONABLE_POSSIBILITY,
    )

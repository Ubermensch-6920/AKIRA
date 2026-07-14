"""Tests for the NAIC RBC calculation."""

import math
from datetime import date

import pytest

from actuarial_model.assumptions.enums import Framework
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.capital.rbc import RbcInput, calculate
from actuarial_model.models.asset import AssetRecord
from actuarial_model.models.results import ReserveResult, ResultMetadata

VAL_DATE = date(2025, 1, 1)


def _reserve(
    framework: Framework, net: float, legal_entity: str = "ENT-A"
) -> ReserveResult:
    return ReserveResult(
        metadata=ResultMetadata(
            valuation_date=VAL_DATE,
            framework=framework,
            methodology_version="test",
            run_id="RUN-1",
            assumption_set_id="as-test",
        ),
        legal_entity=legal_entity,
        segment="MYGA-RETAIL",
        cohort_id="2024Q1",
        gross_reserve=net,
        ceded_reserve=0.0,
        net_reserve=net,
        components={},
    )


def test_hand_calculation(sample_assumption_set: AssumptionSet, sample_asset: AssetRecord):
    """NAIC-2 bond at 998,000 book + 1M VM-22 net reserve, checked closed-form."""
    reserve = 1_000_000.0
    output = calculate(
        RbcInput(
            assumption_set=sample_assumption_set,
            reserve_results=[_reserve(Framework.STAT_VM22, reserve)],
            assets=[sample_asset],
            valuation_date=VAL_DATE,
        )
    )
    components = output.capital_result.components

    c1 = 0.0126 * 998_000.0
    c2 = 0.005 * reserve
    c3 = 0.0077 * reserve
    c4 = 0.0005 * reserve
    expected_acl = 0.5 * (c4 + math.sqrt((c1 + c3) ** 2 + c2**2))

    assert components["c1_asset_risk"] == pytest.approx(c1)
    assert components["c2_insurance_risk"] == pytest.approx(c2)
    assert components["c3_interest_rate_risk"] == pytest.approx(c3)
    assert components["c4_business_risk"] == pytest.approx(c4)
    assert output.capital_result.capital_amount == pytest.approx(expected_acl)


def test_prefers_vm22_over_carvm(sample_assumption_set: AssumptionSet):
    output = calculate(
        RbcInput(
            assumption_set=sample_assumption_set,
            reserve_results=[
                _reserve(Framework.STAT_CARVM, 2_000_000.0),
                _reserve(Framework.STAT_VM22, 1_000_000.0),
            ],
        )
    )
    components = output.capital_result.components
    assert components["statutory_reserve_base"] == pytest.approx(1_000_000.0)
    assert components["reserve_framework_used"] == "STAT_VM22"


def test_falls_back_to_carvm(sample_assumption_set: AssumptionSet):
    output = calculate(
        RbcInput(
            assumption_set=sample_assumption_set,
            reserve_results=[
                _reserve(Framework.STAT_CARVM, 2_000_000.0),
                _reserve(Framework.BEL, 1_500_000.0),
            ],
        )
    )
    components = output.capital_result.components
    assert components["statutory_reserve_base"] == pytest.approx(2_000_000.0)
    assert components["reserve_framework_used"] == "STAT_CARVM"


def test_rbc_ratio_with_tac(sample_assumption_set: AssumptionSet):
    output = calculate(
        RbcInput(
            assumption_set=sample_assumption_set,
            reserve_results=[_reserve(Framework.STAT_VM22, 1_000_000.0)],
            total_adjusted_capital=50_000.0,
        )
    )
    components = output.capital_result.components
    assert components["rbc_ratio"] == pytest.approx(
        50_000.0 / output.capital_result.capital_amount
    )


def test_no_tac_means_no_ratio(sample_assumption_set: AssumptionSet):
    output = calculate(
        RbcInput(
            assumption_set=sample_assumption_set,
            reserve_results=[_reserve(Framework.STAT_VM22, 1_000_000.0)],
        )
    )
    assert output.capital_result.components["rbc_ratio"] is None


def test_asset_class_factors(sample_assumption_set: AssumptionSet, sample_asset: AssetRecord):
    """Equity and cash use flat class factors, not the bond designation table."""
    equity = sample_asset.model_copy(
        update={"asset_id": "AST-EQ", "asset_type": "EQUITY", "book_value": 100.0}
    )
    cash = sample_asset.model_copy(
        update={"asset_id": "AST-CASH", "asset_type": "CASH", "book_value": 100.0}
    )
    output = calculate(
        RbcInput(assumption_set=sample_assumption_set, assets=[equity, cash])
    )
    assert output.capital_result.components["c1_asset_risk"] == pytest.approx(
        0.30 * 100.0 + 0.003 * 100.0
    )


def test_metadata_framework(sample_assumption_set: AssumptionSet):
    output = calculate(
        RbcInput(
            assumption_set=sample_assumption_set,
            reserve_results=[_reserve(Framework.STAT_VM22, 1_000.0)],
            run_id="RUN-9",
        )
    )
    metadata = output.capital_result.metadata
    assert metadata.framework is Framework.NAIC_RBC
    assert metadata.run_id == "RUN-9"
    assert output.capital_result.legal_entity == "ENT-A"

"""Tests for the BEL (Best Estimate Liability) module."""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import Framework
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.core.discount import CurvePoint
from actuarial_model.core.seriatim import SeriatimInput
from actuarial_model.core.seriatim import calculate as run_seriatim
from actuarial_model.models.cash_flows import (
    GrossCashFlows,
    MygaCashFlowRecord,
    PolicyCashFlows,
)
from actuarial_model.models.policy import MygaPolicyState
from actuarial_model.standards.bel import BelInput, calculate

VAL_DATE = date(2025, 1, 1)


def _record(
    period: int,
    end: date,
    *,
    death: float = 0.0,
    surrender: float = 0.0,
    withdrawals: float = 0.0,
    maturity: float = 0.0,
) -> MygaCashFlowRecord:
    return MygaCashFlowRecord(
        policy_id="P1",
        period=period,
        period_start_date=end,
        period_end_date=end,
        account_value_bop=0.0,
        interest_credited=0.0,
        partial_withdrawals=withdrawals,
        surrender_charge=0.0,
        mva_adjustment=0.0,
        surrender_benefits=surrender,
        death_benefits=death,
        maturity_benefits=maturity,
        account_value_eop=0.0,
        lives_in_force=1.0,
    )


def _flat_curve(rate: float) -> list[CurvePoint]:
    return [
        CurvePoint(tenor_years=1.0, rate=rate),
        CurvePoint(tenor_years=30.0, rate=rate),
    ]


def test_requires_cash_flows(sample_assumption_set: AssumptionSet):
    with pytest.raises(ValueError, match="gross_cash_flows"):
        calculate(BelInput(assumption_set=sample_assumption_set))


def test_requires_curve_points(sample_assumption_set: AssumptionSet):
    cfs = GrossCashFlows(valuation_date=VAL_DATE, policies=[])
    with pytest.raises(ValueError, match="curve_points"):
        calculate(BelInput(assumption_set=sample_assumption_set, gross_cash_flows=cfs))


def test_zero_rate_curve_equals_undiscounted_sum(sample_assumption_set: AssumptionSet):
    """At a 0% curve, BEL equals the plain sum of outflows."""
    cfs = GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[
            PolicyCashFlows(
                policy_id="P1",
                records=[
                    _record(1, date(2026, 1, 1), death=1_000.0, surrender=500.0),
                    _record(2, date(2027, 1, 1), withdrawals=200.0, maturity=10_000.0),
                ],
            )
        ],
    )
    output = calculate(
        BelInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=cfs,
            curve_points=_flat_curve(0.0),
        )
    )
    assert output.reserve_result.gross_reserve == pytest.approx(11_700.0)


def test_flat_curve_hand_calculation(sample_assumption_set: AssumptionSet):
    """One 10,000 maturity payment one year out at 4% → BEL ≈ 10,000 / 1.04."""
    cfs = GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[
            PolicyCashFlows(
                policy_id="P1",
                records=[_record(1, date(2026, 1, 1), maturity=10_000.0)],
            )
        ],
    )
    output = calculate(
        BelInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=cfs,
            curve_points=_flat_curve(0.04),
        )
    )
    assert output.reserve_result.gross_reserve == pytest.approx(10_000.0 / 1.04, rel=1e-3)


def test_past_cash_flows_excluded(sample_assumption_set: AssumptionSet):
    """Cash flows on or before the valuation date do not contribute."""
    cfs = GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[
            PolicyCashFlows(
                policy_id="P1",
                records=[
                    _record(1, date(2024, 6, 1), death=99_999.0),  # past
                    _record(2, VAL_DATE, death=99_999.0),  # on valuation date
                    _record(3, date(2026, 1, 1), death=1_000.0),  # future
                ],
            )
        ],
    )
    output = calculate(
        BelInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=cfs,
            curve_points=_flat_curve(0.0),
        )
    )
    assert output.reserve_result.gross_reserve == pytest.approx(1_000.0)


def test_metadata_and_components(sample_assumption_set: AssumptionSet):
    cfs = GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[
            PolicyCashFlows(
                policy_id="P1",
                records=[_record(1, date(2026, 1, 1), death=1_000.0)],
            )
        ],
    )
    output = calculate(
        BelInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=cfs,
            curve_points=_flat_curve(0.03),
            run_id="RUN-42",
        )
    )
    result = output.reserve_result
    assert result.metadata.framework is Framework.BEL
    assert result.metadata.run_id == "RUN-42"
    assert result.metadata.assumption_set_id == sample_assumption_set.assumption_set_id
    assert result.net_reserve == result.gross_reserve  # no reinsurance in Phase 1
    assert result.ceded_reserve == 0.0
    assert result.components["policy_count"] == 1
    assert "P1" in result.components["policy_bel"]


def test_ceded_stream_reduces_net(sample_assumption_set: AssumptionSet):
    """A ceded stream discounts on the same curve; net = gross - ceded."""
    gross = GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[
            PolicyCashFlows(
                policy_id="P1",
                records=[_record(1, date(2026, 1, 1), maturity=10_000.0)],
            )
        ],
    )
    ceded = GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[
            PolicyCashFlows(
                policy_id="P1",
                records=[_record(1, date(2026, 1, 1), maturity=5_000.0)],
            )
        ],
    )
    output = calculate(
        BelInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=gross,
            ceded_cash_flows=ceded,
            curve_points=_flat_curve(0.04),
        )
    )
    result = output.reserve_result
    assert result.ceded_reserve == pytest.approx(0.5 * result.gross_reserve, rel=1e-9)
    assert result.net_reserve == pytest.approx(result.gross_reserve - result.ceded_reserve)
    assert result.components["policy_ceded_bel"]["P1"] == pytest.approx(
        result.ceded_reserve
    )


def test_end_to_end_seriatim_to_bel(sample_assumption_set: AssumptionSet):
    """Full Phase 1 pipeline: policy → seriatim projection → BEL discounting."""
    policy = MygaPolicyState(
        policy_id="E2E-1",
        issue_date=date(2025, 1, 1),
        issue_age=60,
        sex="M",
        issue_state="NY",
        legal_entity="ENT-A",
        segment="MYGA-RETAIL",
        cohort_id="2025Q1",
        valuation_date=VAL_DATE,
        single_premium=100_000.0,
        account_value=100_000.0,
        guaranteed_rate=0.03,
        guarantee_period_years=5,
        guarantee_end_date=date(2030, 1, 1),
        surrender_charge_schedule_id="ATHENE_MYG_5",
    )
    seriatim_out = run_seriatim(
        SeriatimInput(
            assumption_set=sample_assumption_set,
            policies=[policy],
            valuation_date=VAL_DATE,
        )
    )
    bel_out = calculate(
        BelInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=seriatim_out.cash_flows,
            policies=[policy],
            valuation_date=VAL_DATE,
            curve_points=_flat_curve(0.04),
        )
    )
    result = bel_out.reserve_result

    # The BEL of a 100k MYGA crediting 3% and discounted at 4% should land
    # in the broad neighbourhood of the premium — sanity band, not exactness.
    assert 70_000.0 < result.gross_reserve < 110_000.0, (
        f"BEL {result.gross_reserve:,.0f} outside sanity band"
    )
    assert result.legal_entity == "ENT-A"
    assert result.segment == "MYGA-RETAIL"
    # Undiscounted outflows must exceed the discounted reserve at positive rates
    assert result.components["total_outflows_undiscounted"] > result.gross_reserve

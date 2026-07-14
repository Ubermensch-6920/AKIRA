"""Tests for the VM-22 (DR + SR) reserve module."""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import CTELevel, Framework, Vm22Component
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.core.discount import CurvePoint
from actuarial_model.models.cash_flows import (
    GrossCashFlows,
    MygaCashFlowRecord,
    PolicyCashFlows,
)
from actuarial_model.standards.stat_vm22 import StatVm22Input, _cte, calculate

VAL_DATE = date(2025, 1, 1)


def _record(period: int, end: date, *, maturity: float = 0.0, death: float = 0.0):
    return MygaCashFlowRecord(
        policy_id="P1",
        period=period,
        period_start_date=end,
        period_end_date=end,
        account_value_bop=0.0,
        interest_credited=0.0,
        partial_withdrawals=0.0,
        surrender_charge=0.0,
        mva_adjustment=0.0,
        surrender_benefits=0.0,
        death_benefits=death,
        maturity_benefits=maturity,
        account_value_eop=0.0,
        lives_in_force=1.0,
    )


def _cfs(records: list[MygaCashFlowRecord]) -> GrossCashFlows:
    return GrossCashFlows(
        valuation_date=VAL_DATE,
        policies=[PolicyCashFlows(policy_id="P1", records=records)],
    )


def _flat_curve(rate: float) -> list[CurvePoint]:
    return [
        CurvePoint(tenor_years=1.0, rate=rate),
        CurvePoint(tenor_years=30.0, rate=rate),
    ]


def test_requires_cash_flows(sample_assumption_set: AssumptionSet):
    with pytest.raises(ValueError, match="gross_cash_flows"):
        calculate(StatVm22Input(assumption_set=sample_assumption_set))


def test_requires_curve_points(sample_assumption_set: AssumptionSet):
    with pytest.raises(ValueError, match="curve_points"):
        calculate(
            StatVm22Input(
                assumption_set=sample_assumption_set,
                gross_cash_flows=_cfs([]),
            )
        )


def test_dr_hand_calculation(sample_assumption_set: AssumptionSet):
    """One 10,000 payment one year out at a flat 4% → DR ≈ 10,000 / 1.04."""
    output = calculate(
        StatVm22Input(
            assumption_set=sample_assumption_set,
            gross_cash_flows=_cfs([_record(1, date(2026, 1, 1), maturity=10_000.0)]),
            curve_points=_flat_curve(0.04),
        )
    )
    dr = output.reserve_result.components["deterministic_reserve"]
    assert dr == pytest.approx(10_000.0 / 1.04, rel=1e-3)


def test_sr_exceeds_dr_under_down_shocks(sample_assumption_set: AssumptionSet):
    """The CTE tail is dominated by rate-down scenarios, so SR > DR and the
    DR_SR_MAX component returns SR."""
    output = calculate(
        StatVm22Input(
            assumption_set=sample_assumption_set,
            gross_cash_flows=_cfs([_record(1, date(2030, 1, 1), maturity=10_000.0)]),
            curve_points=_flat_curve(0.04),
        )
    )
    result = output.reserve_result
    dr = result.components["deterministic_reserve"]
    sr = result.components["stochastic_reserve"]
    assert sr > dr
    assert result.gross_reserve == pytest.approx(sr)


def test_dr_only_component(sample_assumption_set: AssumptionSet):
    assumption_set = sample_assumption_set.model_copy(deep=True)
    assumption_set.stat_vm22.reserve_component = Vm22Component.DR_ONLY
    output = calculate(
        StatVm22Input(
            assumption_set=assumption_set,
            gross_cash_flows=_cfs([_record(1, date(2030, 1, 1), maturity=10_000.0)]),
            curve_points=_flat_curve(0.04),
        )
    )
    result = output.reserve_result
    assert result.gross_reserve == pytest.approx(
        result.components["deterministic_reserve"]
    )


def test_higher_cte_level_gives_higher_sr(sample_assumption_set: AssumptionSet):
    def sr_at(level: CTELevel) -> float:
        assumption_set = sample_assumption_set.model_copy(deep=True)
        assumption_set.stat_vm22.cte_level = level
        output = calculate(
            StatVm22Input(
                assumption_set=assumption_set,
                gross_cash_flows=_cfs(
                    [_record(1, date(2030, 1, 1), maturity=10_000.0)]
                ),
                curve_points=_flat_curve(0.04),
            )
        )
        return output.reserve_result.components["stochastic_reserve"]

    assert sr_at(CTELevel.CTE80) >= sr_at(CTELevel.CTE70) >= sr_at(CTELevel.CTE65)


def test_ceded_stream_reduces_net(sample_assumption_set: AssumptionSet):
    gross = _cfs([_record(1, date(2030, 1, 1), maturity=10_000.0)])
    ceded = _cfs([_record(1, date(2030, 1, 1), maturity=4_000.0)])
    output = calculate(
        StatVm22Input(
            assumption_set=sample_assumption_set,
            gross_cash_flows=gross,
            ceded_cash_flows=ceded,
            curve_points=_flat_curve(0.04),
        )
    )
    result = output.reserve_result
    assert result.ceded_reserve == pytest.approx(0.4 * result.gross_reserve, rel=1e-9)
    assert result.net_reserve == pytest.approx(
        result.gross_reserve - result.ceded_reserve
    )


def test_metadata(sample_assumption_set: AssumptionSet):
    output = calculate(
        StatVm22Input(
            assumption_set=sample_assumption_set,
            gross_cash_flows=_cfs([_record(1, date(2026, 1, 1), maturity=1_000.0)]),
            curve_points=_flat_curve(0.03),
            run_id="RUN-7",
        )
    )
    metadata = output.reserve_result.metadata
    assert metadata.framework is Framework.STAT_VM22
    assert metadata.run_id == "RUN-7"
    assert output.reserve_result.components["cte_level"] == "CTE70"


def test_cte_helper():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    # CTE70 → worst 30% of 10 = top 3 values → mean(10, 9, 8) = 9
    assert _cte(values, 0.70) == pytest.approx(9.0)
    # CTE80 → worst 20% = top 2 → mean(10, 9) = 9.5
    assert _cte(values, 0.80) == pytest.approx(9.5)
    assert _cte([], 0.70) == 0.0

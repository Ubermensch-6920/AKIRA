"""Tests for the Bermuda EBS (technical provisions + risk margin) module."""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import (
    EbsIlliquidityPremium,
    EbsTPApproach,
    Framework,
)
from actuarial_model.assumptions.sets import AssumptionSet
from actuarial_model.core.discount import CurvePoint
from actuarial_model.models.cash_flows import (
    GrossCashFlows,
    MygaCashFlowRecord,
    PolicyCashFlows,
)
from actuarial_model.standards.ebs import EbsInput, calculate

VAL_DATE = date(2025, 1, 1)


def _record(period: int, end: date, *, maturity: float = 0.0) -> MygaCashFlowRecord:
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
        death_benefits=0.0,
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


def _one_payment() -> GrossCashFlows:
    return _cfs([_record(1, date(2026, 1, 1), maturity=10_000.0)])


def test_requires_cash_flows(sample_assumption_set: AssumptionSet):
    with pytest.raises(ValueError, match="gross_cash_flows"):
        calculate(EbsInput(assumption_set=sample_assumption_set))


def test_requires_curve_points(sample_assumption_set: AssumptionSet):
    with pytest.raises(ValueError, match="curve_points"):
        calculate(
            EbsInput(assumption_set=sample_assumption_set, gross_cash_flows=_cfs([]))
        )


def test_hand_calculation_with_illiquidity_premium(sample_assumption_set: AssumptionSet):
    """4% curve + 50bps IP → EBS BEL = 10,000 / 1.045; TP = BEL + RM."""
    output = calculate(
        EbsInput(
            assumption_set=sample_assumption_set,
            gross_cash_flows=_one_payment(),
            curve_points=_flat_curve(0.04),
        )
    )
    tp = output.technical_provisions
    ebs_bel = tp.components["ebs_bel"]
    assert ebs_bel == pytest.approx(10_000.0 / 1.045, rel=1e-3)
    assert tp.gross_reserve == pytest.approx(
        ebs_bel + tp.components["risk_margin"], rel=1e-9
    )
    assert tp.metadata.framework is Framework.EBS
    assert output.risk_margin.gross_reserve == pytest.approx(
        tp.components["risk_margin"]
    )


def test_zero_illiquidity_premium_matches_raw_curve(sample_assumption_set: AssumptionSet):
    assumption_set = sample_assumption_set.model_copy(deep=True)
    assumption_set.ebs.illiquidity_premium = EbsIlliquidityPremium.ZERO
    output = calculate(
        EbsInput(
            assumption_set=assumption_set,
            gross_cash_flows=_one_payment(),
            curve_points=_flat_curve(0.04),
        )
    )
    assert output.technical_provisions.components["ebs_bel"] == pytest.approx(
        10_000.0 / 1.04, rel=1e-3
    )


def test_reinsurance_haircut_applied(sample_assumption_set: AssumptionSet):
    """40% ceded with a 10% BMA haircut → ceded TP = 36% of gross TP."""
    assumption_set = sample_assumption_set.model_copy(deep=True)
    assumption_set.reinsurance.bma_default_haircut_pct = 0.10
    ceded = _cfs([_record(1, date(2026, 1, 1), maturity=4_000.0)])
    output = calculate(
        EbsInput(
            assumption_set=assumption_set,
            gross_cash_flows=_one_payment(),
            ceded_cash_flows=ceded,
            curve_points=_flat_curve(0.04),
        )
    )
    tp = output.technical_provisions
    assert tp.components["reinsurance_haircut_pct"] == 0.10
    assert tp.ceded_reserve == pytest.approx(0.4 * 0.9 * tp.gross_reserve, rel=1e-9)


def test_haircut_disabled(sample_assumption_set: AssumptionSet):
    assumption_set = sample_assumption_set.model_copy(deep=True)
    assumption_set.ebs.apply_reinsurance_haircut = False
    assumption_set.reinsurance.bma_default_haircut_pct = 0.10
    ceded = _cfs([_record(1, date(2026, 1, 1), maturity=4_000.0)])
    output = calculate(
        EbsInput(
            assumption_set=assumption_set,
            gross_cash_flows=_one_payment(),
            ceded_cash_flows=ceded,
            curve_points=_flat_curve(0.04),
        )
    )
    tp = output.technical_provisions
    assert tp.ceded_reserve == pytest.approx(0.4 * tp.gross_reserve, rel=1e-9)


# ── Scenario-Based Approach ───────────────────────────────────────────────
def _sba_aset(
    sample_assumption_set: AssumptionSet,
    *,
    spread_cap_bps: float = 100.0,
    default_cost_bps: float = 0.0,
) -> AssumptionSet:
    assumption_set = sample_assumption_set.model_copy(deep=True)
    assumption_set.ebs.tp_approach = EbsTPApproach.SBA
    assumption_set.ebs.sba_spread_cap_bps = spread_cap_bps
    assumption_set.ebs.sba_default_cost_bps = default_cost_bps
    return assumption_set


def _zero_coupon(sample_asset, *, par: float, maturity: date, mv: float):
    """A zero-coupon bond position on the EBS basis."""
    return sample_asset.model_copy(
        update={
            "asset_type": "BOND",
            "coupon_rate": 0.0,
            "par_amount": par,
            "maturity_date": maturity,
            "market_value_ebs": mv,
        }
    )


def test_sba_matched_portfolio_defeases_at_market_value(
    sample_assumption_set: AssumptionSet, sample_asset
):
    """Asset CFs exactly matching the liability: BEL = portfolio MV in every
    scenario (full defeasance — the asset yield is the discount rate)."""
    asset = _zero_coupon(
        sample_asset, par=10_000.0, maturity=date(2027, 1, 1), mv=9_200.0
    )
    output = calculate(
        EbsInput(
            assumption_set=_sba_aset(sample_assumption_set),
            gross_cash_flows=_cfs([_record(1, date(2027, 1, 1), maturity=10_000.0)]),
            curve_points=_flat_curve(0.04),
            assets=[asset],
        )
    )
    tp = output.technical_provisions
    assert tp.components["ebs_bel"] == pytest.approx(9_200.0, rel=1e-9)
    assert tp.components["tp_approach"] == "SBA"
    required = tp.components["scenario_required_assets"]
    assert len(required) == 8
    assert all(v == pytest.approx(9_200.0, rel=1e-9) for v in required.values())


def test_sba_duration_mismatch_raises_requirement(
    sample_assumption_set: AssumptionSet, sample_asset
):
    """Long assets against a short liability: a rate-up scenario governs and
    the requirement exceeds the matched case."""
    long_asset = _zero_coupon(
        sample_asset, par=15_000.0, maturity=date(2035, 1, 1), mv=9_200.0
    )
    output = calculate(
        EbsInput(
            assumption_set=_sba_aset(sample_assumption_set),
            gross_cash_flows=_cfs([_record(1, date(2027, 1, 1), maturity=10_000.0)]),
            curve_points=_flat_curve(0.04),
            assets=[long_asset],
        )
    )
    tp = output.technical_provisions
    required = tp.components["scenario_required_assets"]
    assert tp.components["ebs_bel"] > required["LEVEL"]
    assert tp.components["governing_scenario"] in {"POP_UP", "GRADUAL_UP", "UP_DOWN"}


def test_sba_spread_cap_floor_binds(
    sample_assumption_set: AssumptionSet, sample_asset
):
    """A deep-discount portfolio cannot credit spread beyond the cap: with a
    0bp cap the BEL floors at the base-curve risk-free PV."""
    cheap_asset = _zero_coupon(
        sample_asset, par=10_000.0, maturity=date(2027, 1, 1), mv=5_000.0
    )
    output = calculate(
        EbsInput(
            assumption_set=_sba_aset(sample_assumption_set, spread_cap_bps=0.0),
            gross_cash_flows=_cfs([_record(1, date(2027, 1, 1), maturity=10_000.0)]),
            curve_points=_flat_curve(0.04),
            assets=[cheap_asset],
        )
    )
    tp = output.technical_provisions
    # Matched CFs put every scenario requirement at MV (5,000); the floor —
    # two years of 4% flat forwards with no creditable spread — governs.
    assert tp.components["governing_scenario"] == "SPREAD_CAP_FLOOR"
    assert tp.components["ebs_bel"] == pytest.approx(10_000.0 / 1.04**2, rel=1e-6)


def test_sba_default_cost_increases_bel(
    sample_assumption_set: AssumptionSet, sample_asset
):
    def bel_at(default_cost_bps: float) -> float:
        asset = _zero_coupon(
            sample_asset, par=10_000.0, maturity=date(2027, 1, 1), mv=9_200.0
        )
        output = calculate(
            EbsInput(
                assumption_set=_sba_aset(
                    sample_assumption_set, default_cost_bps=default_cost_bps
                ),
                gross_cash_flows=_cfs(
                    [_record(1, date(2027, 1, 1), maturity=10_000.0)]
                ),
                curve_points=_flat_curve(0.04),
                assets=[asset],
            )
        )
        return output.technical_provisions.components["ebs_bel"]

    assert bel_at(100.0) > bel_at(0.0)


def test_sba_requires_eligible_assets(
    sample_assumption_set: AssumptionSet, sample_asset
):
    cfs = _cfs([_record(1, date(2027, 1, 1), maturity=10_000.0)])
    with pytest.raises(ValueError, match="SBA requires"):
        calculate(
            EbsInput(
                assumption_set=_sba_aset(sample_assumption_set),
                gross_cash_flows=cfs,
                curve_points=_flat_curve(0.04),
            )
        )
    equity_only = sample_asset.model_copy(update={"asset_type": "EQUITY"})
    with pytest.raises(ValueError, match="SBA"):
        calculate(
            EbsInput(
                assumption_set=_sba_aset(sample_assumption_set),
                gross_cash_flows=cfs,
                curve_points=_flat_curve(0.04),
                assets=[equity_only],
            )
        )


def test_sba_ceded_proportion_applies(
    sample_assumption_set: AssumptionSet, sample_asset
):
    """40% ceded stream → 40% of the SBA TP ceded (no haircut configured)."""
    assumption_set = _sba_aset(sample_assumption_set)
    assumption_set.reinsurance.bma_default_haircut_pct = 0.0
    asset = _zero_coupon(
        sample_asset, par=10_000.0, maturity=date(2027, 1, 1), mv=9_200.0
    )
    output = calculate(
        EbsInput(
            assumption_set=assumption_set,
            gross_cash_flows=_cfs([_record(1, date(2027, 1, 1), maturity=10_000.0)]),
            ceded_cash_flows=_cfs([_record(1, date(2027, 1, 1), maturity=4_000.0)]),
            curve_points=_flat_curve(0.04),
            assets=[asset],
        )
    )
    tp = output.technical_provisions
    assert tp.ceded_reserve == pytest.approx(0.4 * tp.gross_reserve, rel=1e-9)

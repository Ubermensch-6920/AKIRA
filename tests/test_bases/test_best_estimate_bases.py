"""Hand-calculated tests for the discounted-outflow measures of every basis.

STAT VM-22 · US GAAP ASC 820 fair value · LDTI LFPB / DAC · EBS BEL / TP.
Cash flows are supplied explicitly (``Projection.from_cash_flows``) so each
expected value is a closed form: amount * (1 + r) ** -tenor(period).
"""

from datetime import date

import pytest

from actuarial_model.assumptions.enums import (
    Basis,
    CTELevel,
    DacBasis,
    EbsIlliquidityPremium,
    EbsTPApproach,
    Fas157DiscountBasis,
    Framework,
    NonPerfRiskAdj,
    RiskMarginMethod,
    Vm22Component,
)
from actuarial_model.assumptions.sets import (
    BelConfig,
    EbsConfig,
    Fas157Config,
    LdtiConfig,
    ReinsuranceConfig,
    StatVm22Config,
)
from actuarial_model.bases.ebs import bel, technical_provisions
from actuarial_model.bases.ldti import dac, lfpb
from actuarial_model.bases.stat import vm22
from actuarial_model.bases.us_gaap import fair_value
from actuarial_model.engine.projection import Projection
from tests.factories import VAL_DATE, flat_curve, payment_tenor, policy, stamp

N = 24


def _vector(**at_period: float) -> list[float]:
    values = [0.0] * N
    for key, amount in at_period.items():
        values[int(key.removeprefix("t"))] = amount
    return values


def _projection(policies: dict[str, dict[str, list[float]]]) -> Projection:
    return Projection.from_cash_flows(
        VAL_DATE,
        policies,
        labels={pid: {"legal_entity": "ENT-A", "segment": "SEG", "cohort_id": "C1"} for pid in policies},
    )


@pytest.fixture
def gross() -> Projection:
    # P1: death 1,000 at t=11 and maturity 10,000 at t=23; P2: surrender 500 at t=5.
    return _projection(
        {
            "P1": {"death_benefits": _vector(t11=1_000.0), "maturity_benefits": _vector(t23=10_000.0)},
            "P2": {"surrender_benefits": _vector(t5=500.0), "partial_withdrawals": _vector(t5=100.0)},
        }
    )


@pytest.fixture
def ceded(gross) -> Projection:
    # 40% of P1 ceded.
    frame = gross.frame.filter(gross.frame["policy_id"] == "P1")
    import polars as pl

    return gross.with_frame(
        frame.with_columns(
            [pl.col(c) * 0.4 for c in ("death_benefits", "maturity_benefits")]
        )
    )


def _pv(rate: float) -> dict[str, float]:
    df = lambda t: (1 + rate) ** -payment_tenor(t)  # noqa: E731
    return {"P1": 1_000.0 * df(11) + 10_000.0 * df(23), "P2": 600.0 * df(5)}


# ── EBS: BEL ────────────────────────────────────────────────────────────────


def test_bel_hand_calculation_and_ceded(gross, ceded):
    result = bel.calculate(gross, ceded, BelConfig(), flat_curve(0.04), stamp())
    pv = _pv(0.04)
    r = result.reserve_result
    assert r.gross_reserve == pytest.approx(pv["P1"] + pv["P2"], rel=1e-12)
    assert r.ceded_reserve == pytest.approx(0.4 * pv["P1"], rel=1e-12)
    assert r.net_reserve == pytest.approx(r.gross_reserve - r.ceded_reserve)
    assert r.metadata.framework is Framework.BEL and r.metadata.basis is Basis.EBS
    assert r.components["total_outflows_undiscounted"] == pytest.approx(11_600.0)
    detail = {d["policy_id"]: d for d in result.policy_detail.to_dicts()}
    assert detail["P1"]["gross"] == pytest.approx(pv["P1"])
    assert detail["P2"]["ceded"] == 0.0


def test_zero_curve_equals_undiscounted_sum(gross):
    result = bel.calculate(gross, None, BelConfig(), flat_curve(0.0), stamp())
    assert result.reserve_result.gross_reserve == pytest.approx(11_600.0)


def test_curve_points_required(gross):
    with pytest.raises(ValueError, match="curve_points"):
        bel.calculate(gross, None, BelConfig(), [], stamp())


# ── EBS: technical provisions ───────────────────────────────────────────────


def test_ebs_tp_hand_calculation(gross):
    config = EbsConfig(illiquidity_premium=EbsIlliquidityPremium.BMA_PUBLISHED)
    tp, rm = technical_provisions.calculate(
        gross, None, config, ReinsuranceConfig(), flat_curve(0.04), stamp()
    )
    pv = _pv(0.045)  # risk-free + 50bp illiquidity premium
    ebs_bel = pv["P1"] + pv["P2"]
    df = lambda t: (1 + 0.045) ** -payment_tenor(t)  # noqa: E731
    duration = (
        1_000 * df(11) * payment_tenor(11) + 10_000 * df(23) * payment_tenor(23) + 600 * df(5) * payment_tenor(5)
    ) / ebs_bel
    risk_margin = 0.06 * 0.03 * ebs_bel * duration
    assert tp.reserve_result.components["ebs_bel"] == pytest.approx(ebs_bel, rel=1e-12)
    assert tp.reserve_result.gross_reserve == pytest.approx(ebs_bel + risk_margin, rel=1e-10)
    assert rm.reserve_result.gross_reserve == pytest.approx(risk_margin, rel=1e-10)
    assert rm.supplementary and not tp.supplementary
    assert tp.policy_detail["gross"].sum() == pytest.approx(ebs_bel + risk_margin)


def test_ebs_zero_illiquidity_premium_matches_bel(gross):
    config = EbsConfig(illiquidity_premium=EbsIlliquidityPremium.ZERO)
    tp, _ = technical_provisions.calculate(
        gross, None, config, ReinsuranceConfig(), flat_curve(0.04), stamp()
    )
    base = bel.calculate(gross, None, BelConfig(), flat_curve(0.04), stamp())
    assert tp.reserve_result.components["ebs_bel"] == pytest.approx(base.reserve_result.gross_reserve)


@pytest.mark.parametrize("apply_haircut, expected_factor", [(True, 0.9), (False, 1.0)])
def test_ebs_reinsurance_haircut(gross, ceded, apply_haircut: bool, expected_factor: float):
    config = EbsConfig(apply_reinsurance_haircut=apply_haircut)
    tp, _ = technical_provisions.calculate(
        gross, ceded, config, ReinsuranceConfig(bma_default_haircut_pct=0.10), flat_curve(0.04), stamp()
    )
    comps = tp.reserve_result.components
    assert comps["ceded_ebs_bel"] == pytest.approx(expected_factor * 0.4 * _pv(0.045)["P1"])
    assert tp.reserve_result.ceded_reserve == pytest.approx(
        tp.reserve_result.gross_reserve * comps["ceded_ebs_bel"] / comps["ebs_bel"]
    )


def test_ebs_sba_and_non_coc_not_implemented(gross):
    with pytest.raises(NotImplementedError, match="SBA"):
        technical_provisions.calculate(
            gross, None, EbsConfig(tp_approach=EbsTPApproach.SBA), ReinsuranceConfig(), flat_curve(0.04), stamp()
        )
    with pytest.raises(NotImplementedError, match="CALM"):
        technical_provisions.calculate(
            gross, None, EbsConfig(risk_margin_method=RiskMarginMethod.CALM), ReinsuranceConfig(), flat_curve(0.04), stamp()
        )


# ── US GAAP: ASC 820 fair value ─────────────────────────────────────────────


def test_fair_value_hand_calculation_ois_zero_npr(gross):
    config = Fas157Config(discount_basis=Fas157DiscountBasis.OIS, non_performance_risk=NonPerfRiskAdj.ZERO)
    r = fair_value.calculate(gross, None, config, flat_curve(0.04), stamp()).reserve_result
    pv = _pv(0.04)
    base = pv["P1"] + pv["P2"]
    assert r.components["base_pv"] == pytest.approx(base, rel=1e-12)
    assert r.components["non_performance_adjustment"] == 0.0
    assert r.gross_reserve == pytest.approx(base + r.components["risk_margin"])
    assert r.metadata.basis is Basis.US_GAAP


def test_single_a_discounts_more_than_ois(gross):
    ois = fair_value.calculate(gross, None, Fas157Config(discount_basis=Fas157DiscountBasis.OIS), flat_curve(0.04), stamp())
    single_a = fair_value.calculate(gross, None, Fas157Config(discount_basis=Fas157DiscountBasis.SINGLE_A), flat_curve(0.04), stamp())
    assert single_a.reserve_result.components["base_pv"] < ois.reserve_result.components["base_pv"]


def test_own_credit_reduces_liability(gross):
    zero = fair_value.calculate(gross, None, Fas157Config(non_performance_risk=NonPerfRiskAdj.ZERO), flat_curve(0.04), stamp())
    own = fair_value.calculate(gross, None, Fas157Config(non_performance_risk=NonPerfRiskAdj.OWN_CREDIT), flat_curve(0.04), stamp())
    pv = _pv(0.045)
    assert own.reserve_result.components["non_performance_adjustment"] == pytest.approx(
        pv["P1"] + pv["P2"] - zero.reserve_result.components["base_pv"], rel=1e-10
    )
    assert own.reserve_result.gross_reserve < zero.reserve_result.gross_reserve


def test_fair_value_ceded_scales_with_base_pv(gross, ceded):
    r = fair_value.calculate(gross, ceded, Fas157Config(), flat_curve(0.04), stamp()).reserve_result
    pv = _pv(0.04)
    assert r.ceded_reserve == pytest.approx(r.gross_reserve * 0.4 * pv["P1"] / (pv["P1"] + pv["P2"]))


def test_fair_value_non_coc_not_implemented(gross):
    with pytest.raises(NotImplementedError):
        fair_value.calculate(gross, None, Fas157Config(risk_margin_method=RiskMarginMethod.EXPLICIT), flat_curve(0.04), stamp())


# ── LDTI: LFPB + DAC ────────────────────────────────────────────────────────


def test_lfpb_hand_calculation_and_npr(gross, ceded):
    policies = [policy("P1", account_value=20_000.0), policy("P2", account_value=5_000.0)]
    r = lfpb.calculate(gross, ceded, policies, LdtiConfig(net_premium_ratio_cap=0.3), flat_curve(0.05), stamp()).reserve_result
    pv = _pv(0.05)
    total = pv["P1"] + pv["P2"]
    assert r.gross_reserve == pytest.approx(total, rel=1e-12)
    assert r.ceded_reserve == pytest.approx(0.4 * pv["P1"], rel=1e-12)
    assert r.components["net_premium_ratio_uncapped"] == pytest.approx(total / 25_000.0)
    assert r.components["net_premium_ratio"] == pytest.approx(0.3)
    assert r.metadata.basis is Basis.LDTI


def test_dac_straight_line():
    p = policy(issue_date=date(2023, 1, 1), guarantee_period_years=5)  # 24 of 60 months elapsed
    result = dac.calculate([p], LdtiConfig(acquisition_cost_pct=0.05), stamp())
    assert result.reserve_result.gross_reserve == pytest.approx(0.05 * 100_000.0 * 36 / 60)
    assert result.supplementary
    assert result.reserve_result.components["sign_convention"] == "ASSET"


def test_dac_zero_without_cost_and_after_term():
    assert dac.calculate([policy()], LdtiConfig(), stamp()).reserve_result.gross_reserve == 0.0
    old = policy(issue_date=date(2018, 1, 1), guarantee_period_years=5)
    assert dac.calculate([old], LdtiConfig(acquisition_cost_pct=0.05), stamp()).reserve_result.gross_reserve == 0.0


def test_dac_egp_not_implemented():
    with pytest.raises(NotImplementedError, match="EGP"):
        dac.calculate([policy()], LdtiConfig(dac_basis=DacBasis.EGP), stamp())


# ── STAT: VM-22 ─────────────────────────────────────────────────────────────


def test_vm22_dr_hand_calculation(gross):
    config = StatVm22Config(reserve_component=Vm22Component.DR_ONLY)
    r = vm22.calculate(gross, None, config, flat_curve(0.04), stamp()).reserve_result
    pv = _pv(0.04)
    assert r.gross_reserve == pytest.approx(pv["P1"] + pv["P2"], rel=1e-12)
    assert r.components["deterministic_reserve"] == pytest.approx(r.gross_reserve)
    assert r.metadata.basis is Basis.STAT


def test_vm22_sr_is_cte_of_scenario_reserves(gross):
    r = vm22.calculate(gross, None, StatVm22Config(cte_level=CTELevel.CTE70), flat_curve(0.04), stamp()).reserve_result
    scenarios = r.components["scenario_reserves"]
    assert len(scenarios) == len(vm22.SCENARIO_SHIFTS)
    assert r.components["stochastic_reserve"] == pytest.approx(vm22.cte(scenarios, 0.70))
    # Down-shocks raise the PV, so SR > DR and DR_SR_MAX reports SR.
    assert r.components["stochastic_reserve"] > r.components["deterministic_reserve"]
    assert r.gross_reserve == pytest.approx(r.components["stochastic_reserve"])
    # SR is allocated to policies pro rata to their DR.
    assert r.gross_reserve == pytest.approx(
        vm22.calculate(gross, None, StatVm22Config(), flat_curve(0.04), stamp()).policy_detail["gross"].sum()
    )


def test_vm22_higher_cte_gives_higher_sr(gross):
    sr = {
        level: vm22.calculate(gross, None, StatVm22Config(cte_level=level), flat_curve(0.04), stamp()).reserve_result.components["stochastic_reserve"]
        for level in (CTELevel.CTE65, CTELevel.CTE80)
    }
    assert sr[CTELevel.CTE80] > sr[CTELevel.CTE65]


def test_vm22_ceded_uses_same_component_rule(gross, ceded):
    r = vm22.calculate(gross, ceded, StatVm22Config(reserve_component=Vm22Component.DR_ONLY), flat_curve(0.04), stamp()).reserve_result
    assert r.ceded_reserve == pytest.approx(0.4 * _pv(0.04)["P1"], rel=1e-12)


def test_cte_helper():
    assert vm22.cte([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.70) == pytest.approx(9.0)
    assert vm22.cte([], 0.7) == 0.0
    assert vm22.cte([5.0], 0.99) == 5.0

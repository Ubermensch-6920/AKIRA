"""
EBS — Technical Provisions (Standard approach).

Projected on the ``ebs.technical_provisions`` assumption block.

Method (Phase 1):
  EBS BEL — best-estimate liability outflows discounted on the supplied
    risk-free curve shifted up by the illiquidity premium (BMA_PUBLISHED /
    INTERNAL use the placeholder constant below; ZERO uses the raw curve).
  Risk margin — cost-of-capital proxy: coc_rate * (capital-ratio proxy *
    EBS BEL) * liability duration, standing in for a projected BSCR runoff
    (ASSUMPTION REQUIRED).
  Technical provisions = EBS BEL + risk margin.
  Reinsurance — the ceded stream is discounted on the same curve; when
    ``apply_reinsurance_haircut`` is set, the ceded credit is reduced by
    ``reinsurance.bma_default_haircut_pct``. The risk margin is held on the
    same gross / ceded proportion as the BEL.

Per-policy detail: the risk margin is a portfolio quantity (portfolio
duration), so policy TPs are the policy EBS BEL scaled pro rata to the total.

Phase 1 simplifications (documented for review):
  - Scenario-Based Approach (SBA) raises NotImplementedError.
  - BSCR stresses (lapse, mortality improvement) are not run — the SCR itself
    is Phase 3 scope (:mod:`.ecr`).
  - Risk margin methods other than COST_OF_CAPITAL raise.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from ...assumptions.enums import (
    EbsIlliquidityPremium,
    EbsTPApproach,
    Framework,
    RiskMarginMethod,
)
from ...assumptions.sets import EbsConfig, ReinsuranceConfig
from ...engine.curves import CurvePoint, build_curve
from ...engine.projection import Projection
from ..common import (
    MeasureResult,
    RunStamp,
    allocate,
    policy_detail,
    pv_by_policy,
    pv_weighted_duration,
    require_curve,
    reserve_result,
)

METHODOLOGY_VERSION = "ebs_v1.0.0"

# ASSUMPTION REQUIRED: placeholder illiquidity premium (decimal) until the
# BMA-published table is wired in.
_ILLIQUIDITY_PREMIUM = {
    EbsIlliquidityPremium.BMA_PUBLISHED: 0.0050,
    EbsIlliquidityPremium.INTERNAL: 0.0050,
    EbsIlliquidityPremium.ZERO: 0.0,
}
# ASSUMPTION REQUIRED: capital per unit of liability for the CoC proxy.
_CAPITAL_RATIO_PROXY = 0.03


def calculate(
    gross: Projection,
    ceded: Projection | None,
    config: EbsConfig,
    reinsurance: ReinsuranceConfig,
    curve_points: Sequence[CurvePoint],
    stamp: RunStamp,
) -> tuple[MeasureResult, MeasureResult]:
    """EBS technical provisions and the (supplementary) risk margin.

    Raises:
        ValueError: If ``curve_points`` is empty.
        NotImplementedError: For the SBA approach or non-CoC risk margins.
    """
    require_curve(curve_points, "EBS")
    if config.tp_approach is not EbsTPApproach.STANDARD:
        raise NotImplementedError(
            f"TP approach {config.tp_approach.value} is not implemented in "
            "Phase 1 — use STANDARD."
        )
    if config.risk_margin_method is not RiskMarginMethod.COST_OF_CAPITAL:
        raise NotImplementedError(
            f"Risk margin method {config.risk_margin_method.value} is not "
            "implemented in Phase 1 — use COST_OF_CAPITAL."
        )

    illiquidity_premium = _ILLIQUIDITY_PREMIUM[config.illiquidity_premium]
    curve = build_curve(curve_points, shift=illiquidity_premium, floor=0.0)

    policy_bel = pv_by_policy(gross, curve)
    ebs_bel = float(policy_bel["pv"].sum())
    duration = pv_weighted_duration(gross, curve)
    risk_margin = config.cost_of_capital_rate * _CAPITAL_RATIO_PROXY * ebs_bel * duration
    gross_tp = ebs_bel + risk_margin

    # ── Ceded credit (haircut per BMA counterparty treatment) ───────────
    haircut_pct = reinsurance.bma_default_haircut_pct if config.apply_reinsurance_haircut else 0.0
    policy_ceded = None
    ceded_bel = 0.0
    if ceded is not None:
        policy_ceded = pv_by_policy(ceded, curve).with_columns(pl.col("pv") * (1.0 - haircut_pct))
        ceded_bel = float(policy_ceded["pv"].sum())
    ceded_tp = gross_tp * (ceded_bel / ebs_bel) if ebs_bel > 0.0 else 0.0

    bel_detail = policy_detail(gross.labels(), policy_bel, policy_ceded)
    tp_detail = allocate(bel_detail, gross_tp, ceded_tp)
    tp_result = reserve_result(
        stamp,
        Framework.EBS,
        METHODOLOGY_VERSION,
        tp_detail,
        {
            "component": "TECHNICAL_PROVISIONS",
            "ebs_bel": ebs_bel,
            "ceded_ebs_bel": ceded_bel,
            "risk_margin": risk_margin,
            "illiquidity_premium": illiquidity_premium,
            "liability_duration_years": duration,
            "tp_approach": config.tp_approach.value,
            "reinsurance_haircut_pct": haircut_pct,
            "allocation": "pro_rata_ebs_bel",
        },
        gross=gross_tp,
        ceded=ceded_tp,
    )

    rm_detail = allocate(bel_detail, risk_margin, 0.0)
    rm_result = reserve_result(
        stamp,
        Framework.EBS,
        METHODOLOGY_VERSION,
        rm_detail,
        {
            "component": "RISK_MARGIN",
            "cost_of_capital_rate": config.cost_of_capital_rate,
            "capital_ratio_proxy": _CAPITAL_RATIO_PROXY,
            "liability_duration_years": duration,
            "allocation": "pro_rata_ebs_bel",
        },
        gross=risk_margin,
        ceded=0.0,
    )
    return (
        MeasureResult(reserve_result=tp_result, policy_detail=tp_detail),
        MeasureResult(reserve_result=rm_result, policy_detail=rm_detail, supplementary=True),
    )

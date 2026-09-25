"""
US GAAP — ASC 820 fair-value liability (formerly FAS 157).

Projected on the ``us_gaap.fas157`` assumption block. Kept separate from
LDTI: ASC 820 is an exit-price measurement, ASC 944 LDTI a locked-in /
current-rate liability — different bases, never summed.

Method (Phase 1):
  Fair value = base PV + risk margin + non-performance adjustment, where
    base PV — projected best-estimate liability outflows discounted on the
      supplied curve shifted by the discount-basis spread (OIS = 0,
      SINGLE_A / RF_ILLIQ = placeholder spreads below).
    risk margin — cost-of-capital proxy: coc_rate * (capital-ratio proxy *
      base PV) * liability duration. Stands in for a full projected-capital
      runoff (ASSUMPTION REQUIRED: capital ratio and spreads).
    non-performance adjustment — own-credit (or prescribed) spread added to
      the discount curve; the PV relief is reported as a negative
      adjustment. ZERO leaves the liability unadjusted.
  Ceded fair value scales the gross fair value by the ceded share of base PV.

Per-policy detail: policy fair values are the policy base PVs scaled pro
rata to the portfolio fair value (the margin uses portfolio duration).

Phase 1 simplifications (documented for review):
  - Risk margin methods CALM and EXPLICIT raise NotImplementedError.
  - ``mortality_loaded`` is not applied — load the ``us_gaap.fas157.mortality``
    block instead, which the engine now projects on directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from ...assumptions.enums import (
    Fas157DiscountBasis,
    Framework,
    NonPerfRiskAdj,
    RiskMarginMethod,
)
from ...assumptions.sets import Fas157Config
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

METHODOLOGY_VERSION = "fas157_v1.0.0"

# ASSUMPTION REQUIRED: placeholder spreads (decimal) over the supplied curve.
_DISCOUNT_BASIS_SPREAD = {
    Fas157DiscountBasis.OIS: 0.0,
    Fas157DiscountBasis.SINGLE_A: 0.0080,
    Fas157DiscountBasis.RF_ILLIQ: 0.0050,
}
_OWN_CREDIT_SPREAD = 0.0050
_PRESCRIBED_NPR_SPREAD = 0.0025
# ASSUMPTION REQUIRED: capital held per unit of liability, for the
# cost-of-capital risk-margin proxy.
_CAPITAL_RATIO_PROXY = 0.03


def calculate(
    gross: Projection,
    ceded: Projection | None,
    config: Fas157Config,
    curve_points: Sequence[CurvePoint],
    stamp: RunStamp,
    measurement_date: date | None = None,
) -> MeasureResult:
    """ASC 820 fair-value liability.

    Raises:
        ValueError: If ``curve_points`` is empty.
        NotImplementedError: For CALM / EXPLICIT risk-margin methods.
    """
    require_curve(curve_points, "FAS157")
    if config.risk_margin_method is not RiskMarginMethod.COST_OF_CAPITAL:
        raise NotImplementedError(
            f"Risk margin method {config.risk_margin_method.value} is not "
            "implemented in Phase 1 — use COST_OF_CAPITAL."
        )

    basis_spread = _DISCOUNT_BASIS_SPREAD[config.discount_basis]
    base_curve = build_curve(curve_points, shift=basis_spread, floor=0.0)

    policy_base = pv_by_policy(gross, base_curve)
    base_pv = float(policy_base["pv"].sum())
    duration = pv_weighted_duration(gross, base_curve)
    risk_margin = config.cost_of_capital_rate * _CAPITAL_RATIO_PROXY * base_pv * duration

    npr_adjustment = 0.0
    if config.non_performance_risk is not NonPerfRiskAdj.ZERO and base_pv != 0.0:
        spread = (
            _OWN_CREDIT_SPREAD
            if config.non_performance_risk is NonPerfRiskAdj.OWN_CREDIT
            else _PRESCRIBED_NPR_SPREAD
        )
        npr_curve = build_curve(curve_points, shift=basis_spread + spread, floor=0.0)
        npr_adjustment = float(pv_by_policy(gross, npr_curve)["pv"].sum()) - base_pv
    gross_fair_value = base_pv + risk_margin + npr_adjustment

    policy_ceded = pv_by_policy(ceded, base_curve) if ceded is not None else None
    ceded_base = float(policy_ceded["pv"].sum()) if policy_ceded is not None else 0.0
    # Margin and own-credit scale proportionally with the ceded share.
    ceded_fair_value = gross_fair_value * (ceded_base / base_pv) if base_pv > 0.0 else 0.0

    detail = allocate(
        policy_detail(gross.labels(), policy_base, policy_ceded),
        gross_fair_value,
        ceded_fair_value,
    )
    result = reserve_result(
        stamp,
        Framework.FAS157,
        METHODOLOGY_VERSION,
        detail,
        {
            "base_pv": base_pv,
            "risk_margin": risk_margin,
            "non_performance_adjustment": npr_adjustment,
            "liability_duration_years": duration,
            "discount_basis": config.discount_basis.value,
            "discount_basis_spread": basis_spread,
            "fair_value_level": config.fair_value_level.value,
            "risk_margin_method": config.risk_margin_method.value,
            "measurement_date": (measurement_date or stamp.valuation_date).isoformat(),
            "allocation": "pro_rata_base_pv",
        },
        gross=gross_fair_value,
        ceded=ceded_fair_value,
    )
    return MeasureResult(reserve_result=result, policy_detail=detail)

"""
EBS Scenario-Based Approach (SBA) best-estimate liability.

Under the SBA the liability discount reflects the yield of the assets
actually backing the block rather than risk-free plus the published
illiquidity premium. Mechanically, for each prescribed interest-rate
scenario the required asset amount is the market value of the portfolio
scaled so its cash flows fund the liability cash flows under that
scenario; the SBA BEL is the greatest requirement across scenarios:

    required(s) = MV(portfolio) * PV_s(liabilities) / PV_s(asset CFs)
    BEL_SBA     = max(max over s of required(s), floor)

where ``floor`` discounts the liabilities on the *base* curve plus
``sba_spread_cap_bps`` — the post-2024 reform cap on the spread benefit
creditable in the discount rate. The floor is struck once on the base
curve (a valuation-basis limit), not per shifted scenario: a matched
portfolio whose implied spread is inside the cap defeases at market
value in every scenario. Asset cash flows are haircut for annual default
and downgrade costs (``sba_default_cost_bps``). When assets and
liabilities are perfectly matched the ratio is 1 in every scenario and
the BEL equals the portfolio's market value — full defeasance.

Phase 1 simplifications (documented for review):
  - The eight scenarios below are NY7-style placeholder paths (level,
    graded up/down, up-down, down-up, pop up/down, steepener).
    ASSUMPTION REQUIRED: replace with the BMA-prescribed SBA scenario
    definitions.
  - Assets are presumed marketable at scenario-consistent values, so
    interim liquidity shortfalls are funded by (costless) asset sales —
    no bid-ask or forced-sale friction. Equivalently only the cumulative
    funding condition binds.
  - Liability cash flows are not re-projected per scenario (no dynamic
    lapse response to the rate path).
  - Liability-side SBA eligibility (BMA lapse-risk and predictability
    criteria for surrenderable business) is not tested here — the block
    is presumed eligible. For a surrenderable MYGA this is a genuine
    judgment gate: document MVA protection and lapse resilience in the
    Approved Actuary sign-off.
  - Only fixed-income-like assets (BOND / STRUCTURED / MORTGAGE) plus
    cash generate cash flows; equities are excluded from the SBA
    portfolio per asset-eligibility rules.
"""

from __future__ import annotations

import math
from datetime import date

from pydantic import BaseModel

from ..assets.valuation import _carrying_value
from ..assumptions.enums import CurveInterpolation, Framework
from ..core.discount import CurvePoint, DiscountCurve
from ..models.asset import AssetRecord
from ..models.cash_flows import GrossCashFlows

_FIXED_INCOME_TYPES = {"BOND", "STRUCTURED", "MORTGAGE"}


def _scenario_shifts(horizon_years: int) -> dict[str, list[float]]:
    """Annual parallel-shift paths for the eight placeholder scenarios.

    Index 0 is projection year 1. ASSUMPTION REQUIRED: replace with the
    BMA-prescribed SBA scenario set.
    """
    years = range(1, horizon_years + 1)
    return {
        "LEVEL": [0.0 for _ in years],
        "GRADUAL_UP": [0.005 * min(t, 10) for t in years],
        "GRADUAL_DOWN": [-0.005 * min(t, 10) for t in years],
        "UP_DOWN": [
            0.01 * t if t <= 5 else max(0.01 * (10 - t), 0.0) for t in years
        ],
        "DOWN_UP": [
            -0.01 * t if t <= 5 else min(-0.01 * (10 - t), 0.0) for t in years
        ],
        "POP_UP": [0.03 for _ in years],
        "POP_DOWN": [-0.03 for _ in years],
        "STEEPENER": [-0.01 if t <= 5 else 0.01 for t in years],
    }


class SbaScenarioDetail(BaseModel):
    """Per-scenario decomposition for audit."""

    scenario: str
    required_assets: float  # MV * PV_s(L)/PV_s(A)


class SbaResult(BaseModel):
    """Output of the SBA best-estimate calculation."""

    bel: float
    governing_scenario: str  # scenario name, or SPREAD_CAP_FLOOR when the floor binds
    portfolio_market_value: float
    spread_cap_floor: float  # PV(L) on the base curve + spread cap
    scenario_details: list[SbaScenarioDetail]
    liability_years: int
    asset_years: int


def sba_best_estimate(
    gross_cash_flows: GrossCashFlows,
    assets: list[AssetRecord],
    curve_points: list[CurvePoint],
    valuation_date: date,
    spread_cap_bps: float,
    default_cost_bps: float,
) -> SbaResult:
    """Compute the SBA best-estimate liability for the block.

    Raises:
        ValueError: If no SBA-eligible assets are supplied, or the
            eligible portfolio produces no cash flows to fund the
            liabilities.
    """
    liability_cfs = _liability_buckets(gross_cash_flows, valuation_date)
    asset_cfs, portfolio_mv = _asset_buckets(assets, valuation_date, default_cost_bps)

    if portfolio_mv <= 0.0:
        raise ValueError(
            "SBA requires the backing asset portfolio — supply SBA-eligible "
            "assets (bonds / structured / mortgages / cash) with positive "
            "EBS market value."
        )
    if not any(cf > 0.0 for cf in asset_cfs):
        raise ValueError("SBA-eligible assets produce no cash flows.")

    horizon = max(len(liability_cfs), len(asset_cfs), 1)
    liability_cfs += [0.0] * (horizon - len(liability_cfs))
    asset_cfs += [0.0] * (horizon - len(asset_cfs))

    forwards = _annual_forwards(curve_points, valuation_date, horizon)
    spread_cap = spread_cap_bps / 10_000.0
    no_shift = [0.0] * horizon

    details: list[SbaScenarioDetail] = []
    for name, shifts in _scenario_shifts(horizon).items():
        v_rf = _discount_factors(forwards, shifts, extra_spread=0.0)
        pv_liabilities = sum(cf * v for cf, v in zip(liability_cfs, v_rf, strict=True))
        pv_assets = sum(cf * v for cf, v in zip(asset_cfs, v_rf, strict=True))
        if pv_assets <= 0.0:
            raise ValueError(
                f"Scenario {name}: asset portfolio has no present value."
            )
        details.append(
            SbaScenarioDetail(
                scenario=name,
                required_assets=portfolio_mv * pv_liabilities / pv_assets,
            )
        )

    # Spread-cap floor: base curve plus the capped spread, struck once.
    v_cap = _discount_factors(forwards, no_shift, extra_spread=spread_cap)
    floor = sum(cf * v for cf, v in zip(liability_cfs, v_cap, strict=True))

    governing = max(details, key=lambda d: d.required_assets)
    if floor > governing.required_assets:
        bel, governing_name = floor, "SPREAD_CAP_FLOOR"
    else:
        bel, governing_name = governing.required_assets, governing.scenario

    return SbaResult(
        bel=bel,
        governing_scenario=governing_name,
        portfolio_market_value=portfolio_mv,
        spread_cap_floor=floor,
        scenario_details=details,
        liability_years=sum(1 for cf in liability_cfs if cf > 0.0),
        asset_years=sum(1 for cf in asset_cfs if cf > 0.0),
    )


def _liability_buckets(
    gross_cash_flows: GrossCashFlows, valuation_date: date
) -> list[float]:
    """Liability outflows bucketed into projection years (year-end paid)."""
    buckets: dict[int, float] = {}
    for policy_cf in gross_cash_flows.policies:
        for record in policy_cf.records:
            if record.period_end_date <= valuation_date:
                continue
            outflow = (
                record.death_benefits
                + record.surrender_benefits
                + record.partial_withdrawals
                + record.maturity_benefits
            )
            if outflow == 0.0:
                continue
            year = _year_bucket(valuation_date, record.period_end_date)
            buckets[year] = buckets.get(year, 0.0) + outflow
    if not buckets:
        return []
    return [buckets.get(y, 0.0) for y in range(1, max(buckets) + 1)]


def _asset_buckets(
    assets: list[AssetRecord], valuation_date: date, default_cost_bps: float
) -> tuple[list[float], float]:
    """Annual portfolio cash flows (default-cost haircut) and EBS market value.

    Bonds / structured / mortgages contribute coupons plus par at
    maturity; cash contributes its value in year 1. Equities are
    excluded (SBA asset-eligibility).
    """
    default_rate = default_cost_bps / 10_000.0
    buckets: dict[int, float] = {}
    portfolio_mv = 0.0

    for asset in assets:
        if asset.asset_type == "CASH":
            mv = _carrying_value(asset, Framework.EBS)
            portfolio_mv += mv
            buckets[1] = buckets.get(1, 0.0) + mv
            continue
        if asset.asset_type not in _FIXED_INCOME_TYPES or asset.maturity_date is None:
            continue  # equities and undated assets are not SBA-eligible

        portfolio_mv += _carrying_value(asset, Framework.EBS)
        maturity_year = max(_year_bucket(valuation_date, asset.maturity_date), 1)
        coupon = (asset.coupon_rate or 0.0) * asset.par_amount
        for year in range(1, maturity_year + 1):
            survival = (1.0 - default_rate) ** year
            cf = coupon * survival
            if year == maturity_year:
                cf += asset.par_amount * survival
            buckets[year] = buckets.get(year, 0.0) + cf

    if not buckets:
        return [], portfolio_mv
    return [buckets.get(y, 0.0) for y in range(1, max(buckets) + 1)], portfolio_mv


def _annual_forwards(
    curve_points: list[CurvePoint], valuation_date: date, horizon: int
) -> list[float]:
    """One-year forward rates implied by the base zero curve."""
    points = sorted(curve_points, key=lambda p: p.tenor_years)
    curve = DiscountCurve(
        valuation_date=valuation_date,
        tenors_years=[p.tenor_years for p in points],
        zero_rates=[p.rate for p in points],
        interpolation=CurveInterpolation.LINEAR,
    )
    accumulations = [
        (1.0 + curve.zero_rate(float(t))) ** t for t in range(horizon + 1)
    ]
    return [accumulations[t] / accumulations[t - 1] - 1.0 for t in range(1, horizon + 1)]


def _discount_factors(
    forwards: list[float], shifts: list[float], extra_spread: float
) -> list[float]:
    """Year-end discount factors along a shifted forward path (rates >= 0)."""
    factors: list[float] = []
    accumulation = 1.0
    for forward, shift in zip(forwards, shifts, strict=True):
        accumulation *= 1.0 + max(forward + shift + extra_spread, 0.0)
        factors.append(1.0 / accumulation)
    return factors


def _year_bucket(valuation_date: date, cash_flow_date: date) -> int:
    """1-based projection-year bucket for a cash flow date."""
    days = (cash_flow_date - valuation_date).days
    return max(math.ceil(days / 365.25), 1)

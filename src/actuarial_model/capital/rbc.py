"""
NAIC Risk-Based Capital (RBC) calculation.

Aggregates C-1 (asset), C-2 (insurance), C-3 (interest-rate), and C-4
(business) risk components into the Authorized Control Level (ACL) RBC,
and — when Total Adjusted Capital is supplied — the ACL RBC ratio.

Method (Phase 1, factor-based):
  C-1  asset risk: per-asset factor * statutory carrying value
       (book_value). Bonds/structured use NAIC-designation factors;
       mortgages, equities, and cash use flat class factors.
  C-2  insurance risk: factor * net statutory reserve.
  C-3  interest-rate risk: factor * net statutory reserve (MYGA with
       surrender charges ~= NAIC low-risk category).
  C-4  business risk: factor * net statutory reserve (premium-based in
       the NAIC formula; reserve-proxied here until premium income is
       carried in the model).
  Covariance:  RBC = C-4 + sqrt((C-1 + C-3)² + C-2²)
  ACL RBC   =  0.5 * RBC

The statutory reserve base prefers VM-22 results, falling back to CARVM,
then to whatever reserve results were supplied.

ASSUMPTION REQUIRED: all factors below are approximations of the NAIC
Life RBC factors and must be replaced with the published factor tables
(including tax adjustment) before production use.
"""

import math
from datetime import date

from pydantic import BaseModel

from ..assumptions.enums import Framework
from ..assumptions.sets import AssumptionSet
from ..models.asset import AssetRecord
from ..models.results import CapitalResult, ReserveResult, ResultMetadata

METHODOLOGY_VERSION = "naic_rbc_v0.1.0"

# C-1 bond factors by NAIC designation (pre-tax approximations).
_C1_BOND_FACTORS = {1: 0.0039, 2: 0.0126, 3: 0.0446, 4: 0.0997, 5: 0.2231, 6: 0.30}
_C1_MORTGAGE_FACTOR = 0.0175
_C1_EQUITY_FACTOR = 0.30
_C1_CASH_FACTOR = 0.003

_C2_RESERVE_FACTOR = 0.005  # annuity insurance risk
_C3_RESERVE_FACTOR = 0.0077  # low-risk category (surrender charges apply)
_C4_RESERVE_FACTOR = 0.0005  # business risk, reserve-proxied


class RbcInput(BaseModel):
    """Inputs to the NAIC RBC calculation."""

    assumption_set: AssumptionSet
    reserve_results: list[ReserveResult] = []
    assets: list[AssetRecord] = []
    valuation_date: date | None = None
    total_adjusted_capital: float | None = None  # enables the ACL RBC ratio
    run_id: str = ""


class RbcOutput(BaseModel):
    """Output of the NAIC RBC calculation."""

    capital_result: CapitalResult


def calculate(inputs: RbcInput) -> RbcOutput:
    """Compute NAIC RBC (C-1 ... C-4, covariance, ACL, optional ratio)."""
    reserve_base, reserve_framework = _statutory_reserve_base(inputs.reserve_results)

    c1 = sum(_c1_charge(asset) for asset in inputs.assets)
    c2 = _C2_RESERVE_FACTOR * reserve_base
    c3 = _C3_RESERVE_FACTOR * reserve_base
    c4 = _C4_RESERVE_FACTOR * reserve_base

    rbc_after_covariance = c4 + math.sqrt((c1 + c3) ** 2 + c2**2)
    acl_rbc = 0.5 * rbc_after_covariance

    rbc_ratio = None
    if inputs.total_adjusted_capital is not None and acl_rbc > 0.0:
        rbc_ratio = inputs.total_adjusted_capital / acl_rbc

    valuation_date = inputs.valuation_date or (
        inputs.reserve_results[0].metadata.valuation_date
        if inputs.reserve_results
        else date.today()
    )
    legal_entities = {r.legal_entity for r in inputs.reserve_results}
    legal_entity = legal_entities.pop() if len(legal_entities) == 1 else "ALL"

    result = CapitalResult(
        metadata=ResultMetadata(
            valuation_date=valuation_date,
            framework=Framework.NAIC_RBC,
            methodology_version=METHODOLOGY_VERSION,
            run_id=inputs.run_id,
            assumption_set_id=inputs.assumption_set.assumption_set_id,
        ),
        legal_entity=legal_entity,
        capital_amount=acl_rbc,
        components={
            "c1_asset_risk": c1,
            "c2_insurance_risk": c2,
            "c3_interest_rate_risk": c3,
            "c4_business_risk": c4,
            "rbc_after_covariance": rbc_after_covariance,
            "acl_rbc": acl_rbc,
            "total_adjusted_capital": inputs.total_adjusted_capital,
            "rbc_ratio": rbc_ratio,
            "statutory_reserve_base": reserve_base,
            "reserve_framework_used": reserve_framework,
            "asset_count": len(inputs.assets),
        },
    )
    return RbcOutput(capital_result=result)


def _statutory_reserve_base(results: list[ReserveResult]) -> tuple[float, str | None]:
    """Net statutory reserve underlying C-2 / C-3 / C-4.

    Prefers VM-22 results, then CARVM, then whatever was supplied — the
    fallbacks keep pre-VM-22 runs and framework-agnostic callers working.
    """
    for framework in (Framework.STAT_VM22, Framework.STAT_CARVM):
        selected = [r for r in results if r.metadata.framework is framework]
        if selected:
            return sum(r.net_reserve for r in selected), framework.value
    if results:
        return sum(r.net_reserve for r in results), "MIXED"
    return 0.0, None


def _c1_charge(asset: AssetRecord) -> float:
    """C-1 charge for a single asset on its statutory carrying value."""
    if asset.asset_type == "CASH":
        factor = _C1_CASH_FACTOR
    elif asset.asset_type == "EQUITY":
        factor = _C1_EQUITY_FACTOR
    elif asset.asset_type == "MORTGAGE":
        factor = _C1_MORTGAGE_FACTOR
    else:  # BOND / STRUCTURED — designation-driven
        factor = _C1_BOND_FACTORS.get(asset.naic_designation, _C1_BOND_FACTORS[6])
    return factor * asset.book_value

"""
Cross-framework consistency validators for an :class:`AssumptionSet`.

These validators enforce relationships that span multiple framework
config blocks (e.g. that a treaty marked ``DEPOSIT_ACCOUNTING`` is not
simultaneously credited under STAT). Single-block validation belongs on
the individual config classes themselves.

This module exposes a single entry point :func:`validate_assumption_set`
which returns a list of :class:`ValidationIssue` records. The Phase 1
implementation enumerates the placeholder rules; concrete checks are
added alongside the calculation logic in subsequent phases.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .enums import EbsIlliquidityPremium, RiskFreeCurve, Vm22Component, Vm22ScenarioSet
from .sets import AssumptionSet


class ValidationIssue(BaseModel):
    """A single cross-framework consistency issue."""

    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    path: str  # dotted path within the AssumptionSet, e.g. "reinsurance.gross_to_net_method"


def validate_assumption_set(assumption_set: AssumptionSet) -> list[ValidationIssue]:
    """
    Run all cross-framework consistency checks on ``assumption_set``.

    Args:
        assumption_set: The master configuration to validate.

    Returns:
        A list of :class:`ValidationIssue` records. An empty list means
        every check passed.
    """
    issues: list[ValidationIssue] = []

    # FAS157_COC_RANGE — cost-of-capital rate should be between 1 % and 20 %
    coc = assumption_set.fas157.cost_of_capital_rate
    if not (0.01 <= coc <= 0.20):
        issues.append(
            ValidationIssue(
                severity="warning",
                code="FAS157_COC_RANGE",
                message=f"fas157.cost_of_capital_rate={coc:.4f} is outside the typical range [0.01, 0.20].",
                path="fas157.cost_of_capital_rate",
            )
        )

    # EBS_COC_RANGE — same check for EBS
    coc_ebs = assumption_set.ebs.cost_of_capital_rate
    if not (0.01 <= coc_ebs <= 0.20):
        issues.append(
            ValidationIssue(
                severity="warning",
                code="EBS_COC_RANGE",
                message=f"ebs.cost_of_capital_rate={coc_ebs:.4f} is outside the typical range [0.01, 0.20].",
                path="ebs.cost_of_capital_rate",
            )
        )

    # BEL_DISCOUNT_MISMATCH — US_TREASURY BEL curve is inconsistent with BMA illiquidity premium
    if (
        assumption_set.bel.risk_free_curve is RiskFreeCurve.US_TREASURY
        and assumption_set.ebs.illiquidity_premium is EbsIlliquidityPremium.BMA_PUBLISHED
    ):
        issues.append(
            ValidationIssue(
                severity="warning",
                code="BEL_DISCOUNT_MISMATCH",
                message=(
                    "bel.risk_free_curve=US_TREASURY conflicts with "
                    "ebs.illiquidity_premium=BMA_PUBLISHED; BMA published spreads "
                    "are calibrated to OIS/swap curves, not Treasuries."
                ),
                path="bel.risk_free_curve",
            )
        )

    # LDTI_NPR_CAP_RANGE — net premium ratio cap must be in (0, 1]
    npr_cap = assumption_set.ldti.net_premium_ratio_cap
    if not (0.0 < npr_cap <= 1.0):
        issues.append(
            ValidationIssue(
                severity="error",
                code="LDTI_NPR_CAP_RANGE",
                message=f"ldti.net_premium_ratio_cap={npr_cap} must be in (0, 1].",
                path="ldti.net_premium_ratio_cap",
            )
        )

    # VM22_CTE_SCENARIO_MISMATCH — loading stochastic scenarios but only computing DR is wasteful
    if (
        assumption_set.stat_vm22.scenario_set is Vm22ScenarioSet.NAIC_10K
        and assumption_set.stat_vm22.reserve_component is Vm22Component.DR_ONLY
    ):
        issues.append(
            ValidationIssue(
                severity="info",
                code="VM22_CTE_SCENARIO_MISMATCH",
                message=(
                    "stat_vm22.scenario_set=NAIC_10K but reserve_component=DR_ONLY; "
                    "the stochastic scenario set will be loaded but not used."
                ),
                path="stat_vm22.reserve_component",
            )
        )

    return issues

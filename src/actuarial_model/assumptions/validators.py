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
    # ASSUMPTION REQUIRED: full rule set pending product-spec finalization.
    raise NotImplementedError("Phase 1 — pending product spec")

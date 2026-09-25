"""
Result records emitted by every framework calculation module.

Each result carries :class:`ResultMetadata` so downstream consumers can
trace any number back to the run, basis, framework, methodology version,
and assumption set that produced it.
"""

from datetime import date
from typing import Any

from pydantic import BaseModel, computed_field

from ..assumptions.enums import Basis, Framework


class ResultMetadata(BaseModel):
    """Stamp attached to every result record."""

    valuation_date: date
    framework: Framework
    methodology_version: str
    run_id: str
    assumption_set_id: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def basis(self) -> Basis:
        """STAT / US_GAAP / LDTI / EBS — derived from the framework."""
        return self.framework.basis


class ReserveResult(BaseModel):
    """A single reserve number with its gross / ceded / net decomposition."""

    metadata: ResultMetadata
    legal_entity: str
    segment: str
    cohort_id: str
    gross_reserve: float
    ceded_reserve: float
    net_reserve: float
    components: dict[str, Any]  # framework-specific decomposition


class CapitalResult(BaseModel):
    """A capital figure (RBC / ECR / stochastic) at the legal-entity level."""

    metadata: ResultMetadata
    legal_entity: str
    capital_amount: float
    components: dict[str, Any]

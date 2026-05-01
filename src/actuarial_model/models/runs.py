"""
Valuation run metadata.

A :class:`ValuationRun` records the request, status, and outcome of a
single end-to-end valuation. Every result row produced under a run links
back to it via :attr:`ResultMetadata.run_id`.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from ..assumptions.enums import Framework


class ValuationRun(BaseModel):
    """Lifecycle record for a valuation execution."""

    run_id: str
    valuation_date: datetime
    assumption_set_id: str
    frameworks: list[Framework]
    status: Literal["PENDING", "RUNNING", "COMPLETE", "FAILED"]
    submitted_by: str
    submitted_at: datetime
    completed_at: datetime | None = None
    notes: str = ""

"""
Asset master ledger CRUD.

Single source of truth for :class:`AssetRecord` rows. Persists to
DuckDB; framework-specific valuation views are built on top of these
records by :mod:`actuarial_model.assets.valuation`.
"""

from pydantic import BaseModel

from ..models.asset import AssetRecord


class AssetLedgerInput(BaseModel):
    """Inputs to the asset ledger CRUD layer."""

    assets: list[AssetRecord]
    # ASSUMPTION REQUIRED: ledger persistence target pending wiring


class AssetLedgerOutput(BaseModel):
    """Acknowledgement of ledger writes."""

    asset_ids: list[str] = []


def calculate(inputs: AssetLedgerInput) -> AssetLedgerOutput:
    """Upsert asset records into the master ledger.

    Raises:
        NotImplementedError: Phase 1 — pending product spec.
    """
    raise NotImplementedError("Phase 1 — pending product spec")

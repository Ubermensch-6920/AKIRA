"""
Asset master ledger CRUD.

Single source of truth for :class:`AssetRecord` rows. Persists to
DuckDB; framework-specific valuation views are built on top of these
records by :mod:`actuarial_model.assets.valuation`.

Records are stored as JSON payloads keyed by ``asset_id``; re-writing an
existing ``asset_id`` replaces the row (upsert semantics).
"""

import duckdb
from pydantic import BaseModel

from ..models.asset import AssetRecord


class AssetLedgerInput(BaseModel):
    """Inputs to the asset ledger CRUD layer."""

    assets: list[AssetRecord]
    db_path: str = "akira.duckdb"
    table_name: str = "asset_ledger"


class AssetLedgerOutput(BaseModel):
    """Acknowledgement of ledger writes."""

    asset_ids: list[str] = []


def calculate(inputs: AssetLedgerInput) -> AssetLedgerOutput:
    """Upsert asset records into the master ledger.

    Returns:
        The ``asset_id`` of every record written, in input order.

    Raises:
        ValueError: If ``table_name`` is not a plain identifier (guards
            against SQL injection through the table name).
    """
    _validate_table_name(inputs.table_name)
    with duckdb.connect(inputs.db_path) as conn:
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {inputs.table_name} "
            "(asset_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        for asset in inputs.assets:
            conn.execute(
                f"INSERT OR REPLACE INTO {inputs.table_name} VALUES (?, ?)",
                [asset.asset_id, asset.model_dump_json()],
            )
    return AssetLedgerOutput(asset_ids=[a.asset_id for a in inputs.assets])


def load_assets(db_path: str, table_name: str = "asset_ledger") -> list[AssetRecord]:
    """Read every asset record back from the ledger (empty if no table)."""
    _validate_table_name(table_name)
    with duckdb.connect(db_path) as conn:
        exists = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()
        if not exists or exists[0] == 0:
            return []
        rows = conn.execute(
            f"SELECT payload FROM {table_name} ORDER BY asset_id"
        ).fetchall()
    return [AssetRecord.model_validate_json(r[0]) for r in rows]


def _validate_table_name(table_name: str) -> None:
    if not table_name.isidentifier():
        raise ValueError(f"table_name {table_name!r} must be a plain identifier.")

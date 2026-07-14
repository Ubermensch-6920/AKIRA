"""
DuckDB-backed persistence for valuation runs and their results.

Runs and result records are stored as JSON payloads keyed by ``run_id``
so the REST layer can return them without re-running the pipeline. The
database location comes from the ``AKIRA_DB_PATH`` environment variable;
it defaults to an in-process, in-memory database (hermetic for tests —
set the env var to a file path for durable storage across restarts).
"""

from __future__ import annotations

import json
import os
import threading
from functools import lru_cache
from typing import Any

import duckdb

from ..models.runs import ValuationRun

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id  TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
    run_id      TEXT NOT NULL,
    result_type TEXT NOT NULL,
    grain       TEXT NOT NULL,
    framework   TEXT NOT NULL,
    payload     TEXT NOT NULL
);
"""


class RunStore:
    """Thread-safe DuckDB store for runs and result records."""

    def __init__(self, db_path: str | None = None) -> None:
        path = db_path or os.environ.get("AKIRA_DB_PATH", ":memory:")
        self._conn = duckdb.connect(path)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(_SCHEMA)

    # ── Runs ─────────────────────────────────────────────────────────────
    def save_run(self, run: ValuationRun) -> None:
        """Insert or replace a run record."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?)",
                [run.run_id, run.model_dump_json()],
            )

    def get_run(self, run_id: str) -> ValuationRun | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM runs WHERE run_id = ?", [run_id]
            ).fetchone()
        return ValuationRun.model_validate_json(row[0]) if row else None

    def list_runs(self) -> list[ValuationRun]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM runs ORDER BY run_id").fetchall()
        return [ValuationRun.model_validate_json(r[0]) for r in rows]

    # ── Results ──────────────────────────────────────────────────────────
    def save_result(
        self,
        run_id: str,
        result_type: str,
        grain: str,
        framework: str,
        payload: dict[str, Any],
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO results VALUES (?, ?, ?, ?, ?)",
                [run_id, result_type, grain, framework, json.dumps(payload, default=str)],
            )

    def list_results(
        self,
        run_id: str | None = None,
        result_type: str | None = None,
        framework: str | None = None,
    ) -> list[dict[str, Any]]:
        """Result rows (payload plus type / grain tags), optionally filtered."""
        clauses, params = [], []
        for column, value in (
            ("run_id", run_id),
            ("result_type", result_type),
            ("framework", framework),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                "SELECT run_id, result_type, grain, framework, payload "
                f"FROM results{where}",
                params,
            ).fetchall()
        return [
            {
                "run_id": r[0],
                "result_type": r[1],
                "grain": r[2],
                "framework": r[3],
                "result": json.loads(r[4]),
            }
            for r in rows
        ]


@lru_cache(maxsize=1)
def get_store() -> RunStore:
    """Process-wide store shared by all routers."""
    return RunStore()

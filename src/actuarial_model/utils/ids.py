"""
ID generators for runs and assumption sets.

IDs are deterministic-style strings combining a prefix with a UUID4
suffix so they sort-by-prefix in DuckDB and stay collision-free.
"""

from __future__ import annotations

import uuid


def new_run_id() -> str:
    """Return a fresh ``run_id`` string."""
    return f"run-{uuid.uuid4().hex}"


def new_assumption_set_id() -> str:
    """Return a fresh ``assumption_set_id`` string."""
    return f"as-{uuid.uuid4().hex}"


def new_treaty_id() -> str:
    """Return a fresh ``treaty_id`` string."""
    return f"trt-{uuid.uuid4().hex}"

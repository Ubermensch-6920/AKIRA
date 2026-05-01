"""Runs router — submit, list, and inspect valuation runs."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_runs() -> list[dict]:
    """List valuation runs. Stub — returns empty list in Phase 1."""
    return []

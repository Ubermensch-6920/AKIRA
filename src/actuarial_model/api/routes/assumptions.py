"""Assumptions router — manage assumption sets."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_assumption_sets() -> list[dict]:
    """List assumption sets. Stub — returns empty list in Phase 1."""
    return []

"""Results router — fetch reserve / capital results for a run."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_results() -> list[dict]:
    """List result records. Stub — returns empty list in Phase 1."""
    return []

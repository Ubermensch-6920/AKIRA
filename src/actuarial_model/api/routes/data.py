"""Data router — manage seriatim, asset, and treaty inputs."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_data_sources() -> list[dict]:
    """List loaded input data sources. Stub — returns empty list in Phase 1."""
    return []

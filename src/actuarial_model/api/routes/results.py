"""Results router — fetch reserve / capital results for a run."""

from fastapi import APIRouter, HTTPException

from ...assumptions.enums import Basis
from ..store import get_store

router = APIRouter()


@router.get("/")
def list_results(
    run_id: str | None = None,
    result_type: str | None = None,
    basis: Basis | None = None,
    framework: str | None = None,
) -> list[dict]:
    """List persisted result records, optionally filtered.

    Query params:
        run_id: restrict to one run.
        result_type: RESERVE | RESERVE_AGGREGATE | CAPITAL.
        basis: STAT | US_GAAP | LDTI | EBS.
        framework: e.g. BEL, STAT_CARVM, STAT_VM22, NAIC_RBC.
    """
    return get_store().list_results(
        run_id=run_id,
        result_type=result_type,
        basis=basis.value if basis else None,
        framework=framework,
    )


@router.get("/{run_id}")
def results_for_run(run_id: str) -> list[dict]:
    """All result records for one run (404 if the run is unknown)."""
    store = get_store()
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id {run_id!r}")
    return store.list_results(run_id=run_id)


@router.get("/{run_id}/policies")
def policy_results_for_run(
    run_id: str,
    basis: Basis | None = None,
    framework: str | None = None,
    policy_id: str | None = None,
) -> list[dict]:
    """Per-policy results for one run (404 if the run is unknown)."""
    store = get_store()
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id {run_id!r}")
    return store.list_policy_results(
        run_id, basis=basis.value if basis else None, framework=framework, policy_id=policy_id
    )

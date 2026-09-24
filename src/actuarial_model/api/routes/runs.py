"""Runs router — submit, list, and inspect valuation runs.

POST /runs executes :func:`actuarial_model.pipeline.run_valuation`
synchronously — gaspatchio projection per basis assumption block →
reinsurance → STAT / US GAAP / LDTI / EBS measures → aggregation → RBC —
and persists the run record, every result row (tagged with its basis), and
the per-policy results to the DuckDB store. Supplementary results (LDTI DAC,
EBS risk margin) are persisted and returned but excluded from aggregation.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ...assumptions.sets import AssumptionSet
from ...models.runs import ValuationRun
from ...pipeline import ValuationOutput, run_valuation
from ...utils.ids import new_assumption_set_id, new_run_id
from ..schemas.runs import BasisSummary, RunRequest, RunResponse
from ..store import get_store

router = APIRouter()


@router.get("/")
def list_runs() -> list[dict]:
    """List valuation runs recorded in the store."""
    return [run.model_dump(mode="json") for run in get_store().list_runs()]


@router.get("/{run_id}")
def get_run(run_id: str) -> dict:
    """Fetch a single run record."""
    run = get_store().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id {run_id!r}")
    return run.model_dump(mode="json")


@router.post("/", status_code=201)
def submit_run(request: RunRequest) -> RunResponse:
    """Execute a valuation run end-to-end and persist its results."""
    store = get_store()
    run_id = new_run_id()
    assumption_set = request.assumption_set or _default_assumption_set(request)
    run = ValuationRun(
        run_id=run_id,
        valuation_date=datetime.combine(request.valuation_date, datetime.min.time()),
        assumption_set_id=assumption_set.assumption_set_id,
        frameworks=request.frameworks,
        status="RUNNING",
        submitted_by=request.submitted_by,
        submitted_at=datetime.now(UTC),
        notes=request.notes,
    )
    store.save_run(run)

    try:
        output = run_valuation(
            assumption_set=assumption_set,
            valuation_date=request.valuation_date,
            policies=request.policies,
            curve_points=request.curve_points,
            frameworks=request.frameworks,
            treaties=request.treaties,
            assets=request.assets,
            total_adjusted_capital=request.total_adjusted_capital,
            run_id=run_id,
            projection_horizon_years=request.projection_horizon_years,
        )
        _persist(run_id, output)
    except Exception as exc:
        run.status = "FAILED"
        run.completed_at = datetime.now(UTC)
        store.save_run(run)
        raise HTTPException(status_code=500, detail=f"Run {run_id} failed: {exc}") from exc

    run.status = "COMPLETE"
    run.completed_at = datetime.now(UTC)
    store.save_run(run)
    return RunResponse(
        run=run,
        bases={
            basis.value: BasisSummary(
                reserve_results=[r.model_dump(mode="json") for r in result.reserve_results()],
                capital_results=[c.model_dump(mode="json") for c in result.capital],
            )
            for basis, result in output.bases.items()
        },
        reserve_results=[r.model_dump(mode="json") for r in output.reserve_results],
        capital_results=[c.model_dump(mode="json") for c in output.capital_results],
        aggregation=output.aggregation.model_dump(mode="json"),
        projection_runs=output.projection_runs,
    )


def _default_assumption_set(request: RunRequest) -> AssumptionSet:
    """Default-configured assumption set for callers that don't send one."""
    return AssumptionSet(
        assumption_set_id=new_assumption_set_id(),
        version="0.1.0",
        description="API default assumption set",
        created_by=request.submitted_by,
        created_date=request.valuation_date,
    )


def _persist(run_id: str, output: ValuationOutput) -> None:
    store = get_store()
    for result in output.reserve_results:
        store.save_result(
            run_id,
            result_type="RESERVE",
            grain="RUN_TOTAL",
            basis=result.metadata.basis.value,
            framework=result.metadata.framework.value,
            payload=result.model_dump(mode="json"),
        )
    for grain, results in (
        ("COHORT", output.aggregation.by_cohort),
        ("SEGMENT", output.aggregation.by_segment),
        ("LEGAL_ENTITY", output.aggregation.by_legal_entity),
    ):
        for result in results:
            store.save_result(
                run_id,
                result_type="RESERVE_AGGREGATE",
                grain=grain,
                basis=result.metadata.basis.value,
                framework=result.metadata.framework.value,
                payload=result.model_dump(mode="json"),
            )
    for capital in output.capital_results:
        store.save_result(
            run_id,
            result_type="CAPITAL",
            grain="LEGAL_ENTITY",
            basis=capital.metadata.basis.value,
            framework=capital.metadata.framework.value,
            payload=capital.model_dump(mode="json"),
        )
    store.save_policy_results(run_id, output.policy_results())

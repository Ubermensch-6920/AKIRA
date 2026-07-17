"""Runs router — submit, list, and inspect valuation runs.

POST /runs executes the Phase 1 pipeline synchronously:

    seriatim projection → reinsurance application → framework reserves
    (BEL / CARVM / VM-22 / LDTI / FAS 157 / EBS) → aggregation → NAIC RBC

and persists the run record plus every result row to the DuckDB store,
where GET /results can query them back. Supplementary results (LDTI DAC,
EBS risk margin) are persisted and returned but excluded from the
reserve aggregation — DAC is an asset and the risk margin is already
inside the EBS technical provisions.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ...assumptions.enums import Framework
from ...assumptions.sets import AssumptionSet
from ...capital import rbc
from ...core import aggregation, seriatim
from ...models.results import ReserveResult
from ...models.runs import ValuationRun
from ...reinsurance import application
from ...standards import bel, ebs, fas157, ldti, stat_carvm, stat_vm22
from ...utils.ids import new_assumption_set_id, new_run_id
from ..schemas.runs import RunRequest, RunResponse
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
        response = _execute_pipeline(request, assumption_set, run, run_id)
    except Exception as exc:
        run.status = "FAILED"
        run.completed_at = datetime.now(UTC)
        store.save_run(run)
        raise HTTPException(status_code=500, detail=f"Run {run_id} failed: {exc}") from exc

    run.status = "COMPLETE"
    run.completed_at = datetime.now(UTC)
    store.save_run(run)
    response.run = run
    return response


def _default_assumption_set(request: RunRequest) -> AssumptionSet:
    """Default-configured assumption set for callers that don't send one."""
    return AssumptionSet(
        assumption_set_id=new_assumption_set_id(),
        version="0.1.0",
        description="API default assumption set",
        created_by=request.submitted_by,
        created_date=request.valuation_date,
    )


def _execute_pipeline(
    request: RunRequest,
    assumption_set: AssumptionSet,
    run: ValuationRun,
    run_id: str,
) -> RunResponse:
    store = get_store()

    # ── Projection ───────────────────────────────────────────────────────
    seriatim_out = seriatim.calculate(
        seriatim.SeriatimInput(
            assumption_set=assumption_set,
            policies=list(request.policies),
            valuation_date=request.valuation_date,
            run_id=run_id,
            assets=request.assets,
        )
    )
    gross_cf = seriatim_out.cash_flows

    # ── Reinsurance ──────────────────────────────────────────────────────
    ceded_cf = None
    if request.treaties:
        reins_out = application.calculate(
            application.ReinsuranceApplicationInput(
                assumption_set=assumption_set,
                treaties=request.treaties,
                gross_cash_flows=gross_cf,
                policies=request.policies,
            )
        )
        ceded_cf = reins_out.ceded_cash_flows

    # ── Framework reserves ───────────────────────────────────────────────
    # Primary results feed the aggregation; supplementary results (DAC,
    # EBS risk margin) are persisted and returned alongside them.
    reserve_results: list[ReserveResult] = []
    supplementary_results: list[ReserveResult] = []
    if Framework.BEL in request.frameworks:
        reserve_results.append(
            bel.calculate(
                bel.BelInput(
                    assumption_set=assumption_set,
                    gross_cash_flows=gross_cf,
                    ceded_cash_flows=ceded_cf,
                    policies=request.policies,
                    valuation_date=request.valuation_date,
                    curve_points=request.curve_points,
                    run_id=run_id,
                )
            ).reserve_result
        )
    if Framework.STAT_CARVM in request.frameworks:
        reserve_results.append(
            stat_carvm.calculate(
                stat_carvm.StatCarvmInput(
                    assumption_set=assumption_set,
                    gross_cash_flows=gross_cf,
                    policies=request.policies,
                    valuation_date=request.valuation_date,
                    run_id=run_id,
                )
            ).reserve_result
        )
    if Framework.STAT_VM22 in request.frameworks:
        reserve_results.append(
            stat_vm22.calculate(
                stat_vm22.StatVm22Input(
                    assumption_set=assumption_set,
                    gross_cash_flows=gross_cf,
                    ceded_cash_flows=ceded_cf,
                    policies=request.policies,
                    valuation_date=request.valuation_date,
                    curve_points=request.curve_points,
                    run_id=run_id,
                )
            ).reserve_result
        )
    if Framework.LDTI in request.frameworks:
        ldti_out = ldti.calculate(
            ldti.LdtiInput(
                assumption_set=assumption_set,
                gross_cash_flows=gross_cf,
                ceded_cash_flows=ceded_cf,
                policies=request.policies,
                valuation_date=request.valuation_date,
                curve_points=request.curve_points,
                run_id=run_id,
            )
        )
        reserve_results.append(ldti_out.lfpb_result)
        supplementary_results.append(ldti_out.dac_result)
    if Framework.FAS157 in request.frameworks:
        reserve_results.append(
            fas157.calculate(
                fas157.Fas157Input(
                    assumption_set=assumption_set,
                    gross_cash_flows=gross_cf,
                    ceded_cash_flows=ceded_cf,
                    policies=request.policies,
                    valuation_date=request.valuation_date,
                    curve_points=request.curve_points,
                    run_id=run_id,
                )
            ).reserve_result
        )
    if Framework.EBS in request.frameworks:
        ebs_out = ebs.calculate(
            ebs.EbsInput(
                assumption_set=assumption_set,
                gross_cash_flows=gross_cf,
                ceded_cash_flows=ceded_cf,
                policies=request.policies,
                valuation_date=request.valuation_date,
                curve_points=request.curve_points,
                assets=request.assets,  # backing portfolio when tp_approach = SBA
                run_id=run_id,
            )
        )
        reserve_results.append(ebs_out.technical_provisions)
        supplementary_results.append(ebs_out.risk_margin)

    for result in reserve_results + supplementary_results:
        store.save_result(
            run_id,
            result_type="RESERVE",
            grain="RUN_TOTAL",
            framework=result.metadata.framework.value,
            payload=result.model_dump(mode="json"),
        )

    # ── Aggregation ──────────────────────────────────────────────────────
    agg_out = aggregation.calculate(
        aggregation.AggregationInput(seriatim_results=reserve_results)
    )
    aggregation_payload = agg_out.model_dump(mode="json")
    for grain, results in (
        ("COHORT", agg_out.by_cohort),
        ("SEGMENT", agg_out.by_segment),
        ("LEGAL_ENTITY", agg_out.by_legal_entity),
    ):
        for result in results:
            store.save_result(
                run_id,
                result_type="RESERVE_AGGREGATE",
                grain=grain,
                framework=result.metadata.framework.value,
                payload=result.model_dump(mode="json"),
            )

    # ── Capital ──────────────────────────────────────────────────────────
    capital_results = []
    if Framework.NAIC_RBC in request.frameworks:
        rbc_out = rbc.calculate(
            rbc.RbcInput(
                assumption_set=assumption_set,
                reserve_results=reserve_results,
                assets=request.assets,
                valuation_date=request.valuation_date,
                total_adjusted_capital=request.total_adjusted_capital,
                run_id=run_id,
            )
        )
        capital_results.append(rbc_out.capital_result)
        store.save_result(
            run_id,
            result_type="CAPITAL",
            grain="LEGAL_ENTITY",
            framework=Framework.NAIC_RBC.value,
            payload=rbc_out.capital_result.model_dump(mode="json"),
        )

    return RunResponse(
        run=run,
        reserve_results=[
            r.model_dump(mode="json") for r in reserve_results + supplementary_results
        ],
        capital_results=[c.model_dump(mode="json") for c in capital_results],
        aggregation=aggregation_payload,
    )

"""End-to-end API tests: POST /runs pipeline and /results retrieval."""


import pytest
from fastapi.testclient import TestClient

from actuarial_model.api.main import app

client = TestClient(app)

VAL_DATE = "2025-01-01"


def _policy(policy_id: str, treaty_id: str | None = None) -> dict:
    return {
        "policy_id": policy_id,
        "product_type": "MYGA",
        "issue_date": "2025-01-01",
        "issue_age": 60,
        "sex": "M",
        "issue_state": "NY",
        "legal_entity": "ENT-A",
        "segment": "MYGA-RETAIL",
        "cohort_id": "2025Q1",
        "valuation_date": VAL_DATE,
        "single_premium": 100_000.0,
        "account_value": 100_000.0,
        "guaranteed_rate": 0.03,
        "guarantee_period_years": 5,
        "guarantee_end_date": "2030-01-01",
        "surrender_charge_schedule_id": "ATHENE_MYG_5",
        "reinsurance_treaty_id": treaty_id,
    }


def _treaty(treaty_id: str = "TRT-1") -> dict:
    return {
        "treaty_id": treaty_id,
        "treaty_name": "QS 50",
        "counterparty": "Sample Re",
        "counterparty_rating": "A+",
        "auth_status": "AUTHORIZED",
        "treaty_type": "QUOTA_SHARE",
        "effective_date": "2024-01-01",
        "quota_share_pct": 0.50,
        "risk_transfer_method": "REASONABLE_POSSIBILITY",
    }


def _run_body(**overrides) -> dict:
    body = {
        "valuation_date": VAL_DATE,
        "policies": [_policy("POL-1")],
        "curve_points": [
            {"tenor_years": 1.0, "rate": 0.04},
            {"tenor_years": 30.0, "rate": 0.04},
        ],
    }
    body.update(overrides)
    return body


@pytest.fixture(scope="module")
def completed_run() -> dict:
    response = client.post("/runs/", json=_run_body())
    assert response.status_code == 201, response.text
    return response.json()


def test_run_completes_with_all_phase1_frameworks(completed_run: dict):
    run = completed_run["run"]
    assert run["status"] == "COMPLETE"
    assert run["completed_at"] is not None

    frameworks = {r["metadata"]["framework"] for r in completed_run["reserve_results"]}
    assert frameworks == {"BEL", "STAT_CARVM", "STAT_VM22", "LDTI", "FAS157", "EBS"}
    # 6 primary results + LDTI DAC + EBS risk margin
    assert len(completed_run["reserve_results"]) == 8
    assert len(completed_run["capital_results"]) == 1
    assert completed_run["capital_results"][0]["metadata"]["framework"] == "NAIC_RBC"

    aggregation = completed_run["aggregation"]
    # One row per framework; DAC / risk margin stay out of the rollup.
    assert len(aggregation["by_legal_entity"]) == 6


def test_run_is_listed_and_fetchable(completed_run: dict):
    run_id = completed_run["run"]["run_id"]
    listed = client.get("/runs/").json()
    assert run_id in {r["run_id"] for r in listed}

    fetched = client.get(f"/runs/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "COMPLETE"

    assert client.get("/runs/run-does-not-exist").status_code == 404


def test_results_persisted_and_filterable(completed_run: dict):
    run_id = completed_run["run"]["run_id"]

    all_rows = client.get(f"/results/{run_id}").json()
    types = {row["result_type"] for row in all_rows}
    assert types == {"RESERVE", "RESERVE_AGGREGATE", "CAPITAL"}

    bel_rows = client.get(
        "/results/", params={"run_id": run_id, "framework": "BEL", "result_type": "RESERVE"}
    ).json()
    assert len(bel_rows) == 1
    assert bel_rows[0]["result"]["gross_reserve"] > 0

    assert client.get("/results/run-does-not-exist").status_code == 404


def test_run_with_reinsurance_cedes_half_of_bel():
    body = _run_body(
        policies=[_policy("POL-RE", treaty_id="TRT-1")],
        treaties=[_treaty("TRT-1")],
    )
    response = client.post("/runs/", json=body)
    assert response.status_code == 201, response.text

    bel_result = next(
        r
        for r in response.json()["reserve_results"]
        if r["metadata"]["framework"] == "BEL"
    )
    assert bel_result["ceded_reserve"] == pytest.approx(
        0.5 * bel_result["gross_reserve"], rel=1e-9
    )


def test_unknown_framework_rejected():
    response = client.post("/runs/", json=_run_body(frameworks=["NOT_A_FRAMEWORK"]))
    assert response.status_code == 422

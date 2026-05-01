"""Smoke test: FastAPI app boots and exposes /health."""

from fastapi.testclient import TestClient

from actuarial_model.api.main import app


def test_health() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "actuarial_model"

"""
FastAPI app entry point.

Exposes a health check and mounts the runs / results / assumptions /
data routers. CORS is configured to allow the Vite dev server on
``http://localhost:5173`` for local frontend development.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import assumptions, data, results, runs

app = FastAPI(
    title="AKIRA Actuarial Model",
    version="0.1.0",
    description="Multi-framework actuarial reserving and capital model (MYGA-first).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Return a simple liveness payload."""
    return {"status": "ok", "service": "actuarial_model", "version": "0.1.0"}


app.include_router(runs.router, prefix="/runs", tags=["runs"])
app.include_router(results.router, prefix="/results", tags=["results"])
app.include_router(assumptions.router, prefix="/assumptions", tags=["assumptions"])
app.include_router(data.router, prefix="/data", tags=["data"])

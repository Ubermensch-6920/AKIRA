# AKIRA — Actuarial Reserving & Capital Model

Multi-framework actuarial reserving and capital model. MYGA-first, with an
architecture extensible to PRT/SPIA, FIA, VA, and ULSG.

## Status

**Phase 1 complete, rewired onto [gaspatchio](https://gaspatchio.dev/latest/).**
MYGA cash flows are projected by a vectorised gaspatchio `ActuarialFrame`
model: one row per policy, one list element per month, no per-policy loops.
Results are demarcated into four bases: **STAT**, **US GAAP**, **LDTI** and
**EBS**. Placeholder assumptions are flagged `ASSUMPTION REQUIRED` throughout.

## Phase 1 Scope

- **Products:** MYGA
- **Reinsurance:** Quota share only

## Roadmap

| Phase | Products added         | Reinsurance added                                       |
|-------|------------------------|---------------------------------------------------------|
| 1     | MYGA                   | Quota share                                             |
| 2     | PRT, SPIA, FIA         | Coinsurance, ModCo, Funds Withheld, YRT, Excess of Loss |
| 3     | VA, ULSG               | —                                                       |

## Bases & Frameworks

| Basis       | Measures                                                   | Assumption block         |
|-------------|------------------------------------------------------------|--------------------------|
| **STAT**    | CARVM (Pre-VM-22), VM-22 (DR + SR), NAIC RBC               | `assumption_set.stat`    |
| **US GAAP** | ASC 820 fair value (FAS 157)                               | `assumption_set.us_gaap` |
| **LDTI**    | ASC 944 LFPB, DAC                                          | `assumption_set.ldti`    |
| **EBS**     | BEL (risk-free), technical provisions + risk margin, ECR*  | `assumption_set.ebs`     |

\* ECR / BSCR is a Phase 3 stub. Stochastic capital (`capital/stochastic.py`) is cross-basis.

Every result carries `metadata.basis`. Each basis projects on its own
assumption block, and results from different bases are never summed.

## Architecture (data flow)

```
 seriatim policies ──► gaspatchio projection (per basis assumption block, cached)
                              │
                              ▼
                     reinsurance split (gross / ceded / net)
                              │
      ┌───────────────┬───────┴───────┬──────────────────┐
      ▼               ▼               ▼                  ▼
    STAT           US GAAP          LDTI               EBS
  CARVM · VM-22   ASC 820 FV      LFPB · DAC       BEL · TP (+RM)
  → NAIC RBC
      │               │               │                  │
      └───────────────┴───────┬───────┴──────────────────┘
                              ▼
          aggregation per (basis, framework): cohort → segment → legal entity
                              ▼
          DuckDB: runs · results (basis-tagged) · policy_results
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module map, the gaspatchio
model, and the methodology changes made in the rewire.

## Quick Start

### Backend

```bash
# Python 3.12 environment (gaspatchio requires >= 3.12)
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the test suite
pytest

# Run the API locally
uvicorn actuarial_model.api.main:app --reload --port 8000
# → http://localhost:8000/health
```

### Frontend (scaffold only)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Lint & type check

```bash
ruff check .
mypy src/
```

## Directory Map

```
src/actuarial_model/
├── pipeline.py      # run_valuation(): project → reinsure → bases → aggregate
├── assumptions/     # enums (Basis, Framework), basis-demarcated AssumptionSet, rate tables
├── engine/          # gaspatchio engine: grid, curves, tables, model points,
│   │                #   Projection carrier, seriatim dispatch, aggregation
│   └── projections/ # myga.py (Phase 1); fia / spia / va / ulsg stubs
├── reinsurance/     # frame-based quota share + application; Phase 2 stubs
├── bases/           # ← demarcation
│   ├── stat/        #   carvm.py · vm22.py · rbc.py
│   ├── us_gaap/     #   fair_value.py (ASC 820)
│   ├── ldti/        #   lfpb.py · dac.py
│   └── ebs/         #   bel.py · technical_provisions.py · ecr.py (stub)
├── capital/         # stochastic.py (cross-basis stub)
├── assets/          # DuckDB ledger + per-basis carrying values
├── models/          # Pydantic records (policy, asset, treaty, results, runs)
└── api/             # FastAPI: /runs, /results, /results/{run_id}/policies
tests/               # engine · reinsurance · bases (incl. demarcation) · assumptions · API
frontend/            # React + Tailwind scaffold
data/                # input schema docs, outputs
```

## Conventions

- All public data structures are Pydantic v2 `BaseModel`s. No bare dicts
  cross module boundaries.
- Every basis measure exposes `calculate(...) -> MeasureResult` (run-level
  `ReserveResult` + per-policy detail); each basis package exposes `run(ctx, frameworks)`.
- All result records carry `valuation_date`, `framework`,
  `methodology_version`, `run_id`, and `assumption_set_id`.
- `# ASSUMPTION REQUIRED: ...` markers flag inputs awaiting product-spec
  finalization.
- Projections are gaspatchio `ActuarialFrame` models. Cash flows travel as a
  polars frame (one row per policy, `list[f64]` per cash-flow line) on a
  shared monthly grid anchored at the valuation date.
- Every result is stamped with its basis (STAT / US_GAAP / LDTI / EBS);
  results from different bases are never summed.
- gaspatchio `Table`s are content-addressed (`engine/tables.py`); never
  register tables by a fixed name.
- Logging via `logging` (configured in `utils/logging_config.py`), never `print`.

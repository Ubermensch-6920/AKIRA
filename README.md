# AKIRA — Actuarial Reserving & Capital Model

Multi-framework actuarial reserving and capital model. MYGA-first, with an
architecture extensible to PRT/SPIA, FIA, VA, and ULSG.

## Status

**Phase 1 scaffolding only.** This commit ships project structure, Pydantic
data models, module stubs with typed signatures, a tests harness, and the
tooling baseline. **No calculation logic is implemented yet** — every
`calculate(...)` entry point raises `NotImplementedError`. Product specs and
seriatim field definitions arrive in the next prompt.

## Phase 1 Scope

- **Products:** MYGA
- **Reinsurance:** Quota share only

## Roadmap

| Phase | Products added         | Reinsurance added                                       |
|-------|------------------------|---------------------------------------------------------|
| 1     | MYGA                   | Quota share                                             |
| 2     | PRT, SPIA, FIA         | Coinsurance, ModCo, Funds Withheld, YRT, Excess of Loss |
| 3     | VA, ULSG               | —                                                       |

## Frameworks Covered

- **STAT** — Pre-VM-22 CARVM (`STAT_CARVM`) and VM-22 (`STAT_VM22`, DR + SR)
- **GAAP** — ASC 944 LDTI (`LDTI`, LFPB + DAC) and ASC 820 fair value (`FAS157`)
- **Bermuda** — Economic Balance Sheet (`EBS`)
- **Cross-cutting** — Best Estimate Liability (`BEL`)
- **Capital** — NAIC RBC, Bermuda ECR, stochastic capital

## Architecture (data flow)

```
            ┌────────────────┐
            │   Seriatim     │  PolicyState records (per product)
            │   inputs       │  AssetRecord ledger
            │                │  ReinsuranceTreaty registry
            └───────┬────────┘
                    │
                    ▼
            ┌────────────────┐
            │  Projection    │  core/projections/<product>.py
            │  engine        │  → gross cash flows, in-force, decrements
            └───────┬────────┘
                    │
                    ▼
            ┌────────────────┐
            │  Reinsurance   │  reinsurance/application.py
            │  application   │  gross → ceded → net cash flows
            └───────┬────────┘
                    │
                    ▼
            ┌────────────────┐
            │  BEL           │  standards/bel.py
            │  (cross-cut)   │  best-estimate liability discounting
            └───────┬────────┘
                    │
                    ▼
            ┌─────────────────────────────────────────────────────┐
            │  Framework reserves                                 │
            │  STAT_CARVM · STAT_VM22 · LDTI · FAS157 · EBS       │
            └───────┬─────────────────────────────────────────────┘
                    │
                    ▼
            ┌────────────────┐         ┌────────────────┐
            │  Aggregation   │  ───►   │  Capital       │
            │  cohort →      │         │  RBC · ECR ·   │
            │  segment → BS  │         │  stochastic    │
            └───────┬────────┘         └───────┬────────┘
                    │                          │
                    └──────────┬───────────────┘
                               ▼
                       ┌────────────────┐
                       │  Output records │  ReserveResult / CapitalResult
                       │  (DuckDB)       │  every record stamped with
                       │                 │  run_id + assumption_set_id
                       └────────────────┘
```

## Quick Start

### Backend

```bash
# Python 3.11 environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the test harness (smoke tests only — calculations raise NotImplementedError)
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
.
├── pyproject.toml
├── README.md
├── .gitignore
├── .python-version
├── requirements.txt
├── requirements-dev.txt
│
├── src/actuarial_model/
│   ├── models/              # Pydantic data models (no logic)
│   │   ├── policy.py
│   │   ├── asset.py
│   │   ├── reinsurance.py
│   │   ├── results.py
│   │   └── runs.py
│   ├── assumptions/         # Optionality / config
│   │   ├── enums.py
│   │   ├── sets.py
│   │   └── validators.py
│   ├── core/                # Core projection engine
│   │   ├── seriatim.py      # Dispatcher: routes to product engine
│   │   ├── aggregation.py   # Cohort → Segment → BS rollup
│   │   ├── discount.py      # Yield curve + DF utilities
│   │   └── projections/     # Product-specific projection modules
│   │       ├── myga.py      # Phase 1
│   │       ├── fia.py       # Phase 2 stub
│   │       ├── spia.py      # Phase 2 stub
│   │       ├── va.py        # Phase 3 stub
│   │       └── ulsg.py      # Phase 3 stub
│   ├── standards/           # Reserve framework modules
│   │   ├── bel.py
│   │   ├── stat_carvm.py
│   │   ├── stat_vm22.py
│   │   ├── ldti.py
│   │   ├── fas157.py
│   │   └── ebs.py
│   ├── capital/             # Capital frameworks
│   │   ├── rbc.py
│   │   ├── ecr.py
│   │   └── stochastic.py
│   ├── reinsurance/         # Reinsurance treatment
│   │   ├── application.py
│   │   ├── quota_share.py   # Phase 1 implementation
│   │   ├── coinsurance.py   # Phase 2 stub
│   │   ├── modco.py         # Phase 2 stub
│   │   ├── funds_withheld.py
│   │   ├── yrt.py
│   │   ├── excess_of_loss.py
│   │   └── risk_transfer.py
│   ├── assets/              # Asset ledger + valuation views
│   │   ├── ledger.py
│   │   └── valuation.py
│   ├── api/                 # FastAPI layer
│   │   ├── main.py
│   │   ├── routes/{runs,results,assumptions,data}.py
│   │   └── schemas/
│   └── utils/
│       ├── logging_config.py
│       └── ids.py
│
├── frontend/                # React + Tailwind + shadcn (scaffold only)
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── src/{App.jsx,main.jsx,components/}
│
├── data/
│   ├── inputs/schema.md     # Seriatim + asset field definitions
│   └── outputs/
│
└── tests/
    ├── conftest.py
    ├── test_models/
    ├── test_assumptions/
    ├── test_core/
    ├── test_standards/
    ├── test_reinsurance/
    └── test_capital/
```

## Conventions

- All public data structures are Pydantic v2 `BaseModel`s. No bare dicts
  cross module boundaries.
- Every calculation module exposes `calculate(inputs: ModelInput) -> ModelOutput`.
- All result records carry `valuation_date`, `framework`,
  `methodology_version`, `run_id`, and `assumption_set_id`.
- `# ASSUMPTION REQUIRED: ...` markers flag inputs awaiting product-spec
  finalization.
- Calculations are vectorized (numpy / pandas); cash flow arrays use numpy
  arrays with explicit `pd.DatetimeIndex` labels.
- Logging via `logging` (configured in `utils/logging_config.py`), never `print`.

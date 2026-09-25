# AKIRA — Development Progress Tracker

*Last updated: 2026-09-24*

---

## Module Status

| Basis / layer | Module | File(s) | Status | Notes |
|---------------|--------|---------|--------|-------|
| Engine | **MYGA projection (gaspatchio)** | `engine/projections/myga.py` | ✅ Complete | Vectorised ActuarialFrame model; reconciled to scalar reference at 1e-12; AV roll-forward balances |
| Engine | Grid / curves / tables / model points | `engine/grid.py`, `curves.py`, `tables.py`, `model_points.py` | ✅ Complete | Valuation-date monthly grid; gaspatchio `Curve`; content-addressed `Table`s |
| Engine | Projection carrier | `engine/projection.py` | ✅ Complete | One row per policy, `list[f64]` per cash-flow line |
| Engine | Seriatim dispatcher | `engine/seriatim.py` | ✅ Complete | MYGA routed; Phase 2/3 products raise |
| Engine | Aggregation | `engine/aggregation.py` | ✅ Complete | Per-policy → cohort / segment / legal entity, keyed by (basis, framework) |
| Orchestration | Pipeline + valuation context | `pipeline.py`, `bases/context.py` | ✅ Complete | One gaspatchio run per distinct assumption block |
| Assumptions | Basis-demarcated `AssumptionSet` | `assumptions/sets.py`, `enums.py` | ✅ Complete | `stat` · `us_gaap` · `ldti` · `ebs`; per-block mortality levers |
| Assumptions | Rate tables | `assumptions/mortality.py`, `lapse.py`, `withdrawal.py` | ✅ Complete | SOA 2012 IAM + G2, lapse shocks, Athene surrender schedules |
| Reinsurance | Quota share + application | `reinsurance/quota_share.py`, `application.py` | ✅ Complete | Vectorised per-policy treaty share |
| **STAT** | CARVM | `bases/stat/carvm.py` | ✅ Complete | Greatest-PV of guaranteed benefits as a gaspatchio frame |
| **STAT** | VM-22 | `bases/stat/vm22.py` | ✅ Complete | DR + CTE SR (placeholder scenario set) |
| **STAT** | NAIC RBC | `bases/stat/rbc.py` | ✅ Complete | Factor-based; STAT reserves only |
| **US GAAP** | ASC 820 fair value | `bases/us_gaap/fair_value.py` | ✅ Complete | Base PV + CoC RM + own-credit |
| **LDTI** | LFPB | `bases/ldti/lfpb.py` | ✅ Complete | Single-premium NPR mechanics |
| **LDTI** | DAC | `bases/ldti/dac.py` | ✅ Complete | Straight-line; supplementary (asset) |
| **EBS** | BEL | `bases/ebs/bel.py` | ✅ Complete | Risk-free |
| **EBS** | Technical provisions | `bases/ebs/technical_provisions.py` | ✅ Complete | BEL @ rf+IP + CoC RM; BMA haircut on ceded |
| **EBS** | Bermuda ECR | `bases/ebs/ecr.py` | 🔴 Stub | Phase 3 |
| Cross-basis | Stochastic capital | `capital/stochastic.py` | 🔴 Stub | Phase 3 |
| Assets | Ledger + valuation views | `assets/` | ✅ Complete | Carrying value by basis |
| API | Runs / results / policy results | `api/` | ✅ Complete | Basis-grouped responses, `?basis=` filter, `/results/{run_id}/policies` |
| Reinsurance | Coinsurance / ModCo / FWH / YRT / XL | `reinsurance/*.py` | 🔴 Phase 2 | |
| Engine | FIA / SPIA / VA / ULSG | `engine/projections/*.py` | 🔴 Phase 2/3 | |
| Frontend | | `frontend/src/` | 🔴 Stub | Scaffold only |

**Legend:** ✅ Implemented & tested &nbsp;|&nbsp; 🔴 Not started / stub only

---

## Test Coverage Summary

| Area | Test File | Coverage |
|------|-----------|----------|
| MYGA engine | `test_engine/test_myga_projection.py` | Scalar-reference reconciliation, AV balance, crediting, lapse timing, maturity, ROP, charges, basis levers |
| Curves / grid / tables | `test_engine/test_curves.py`, `test_tables_and_grid.py` | Interpolation, extrapolation, shifts/floors, content-addressed tables |
| Seriatim / aggregation | `test_engine/test_seriatim.py`, `test_aggregation.py` | Routing, grains, no framework mixing |
| Reinsurance | `test_reinsurance/test_reinsurance.py` | Split conservation, pairing, validation, Phase 2 guards |
| STAT | `test_bases/test_stat_carvm.py`, `test_stat_rbc.py` | CARVM closed forms; RBC hand calc, STAT-only base |
| VM-22 / FAS 157 / LDTI / BEL / EBS | `test_bases/test_best_estimate_bases.py` | Hand calculations, ceded, haircut, NPR, DAC, CTE |
| Demarcation | `test_bases/test_demarcation.py` | Basis stamping, per-block projection, cache, RBC isolation, aggregation |
| Assumptions / models / assets | `test_assumptions/`, `test_models/`, `test_assets/` | Config validation, rate tables, carrying values |
| API | `test_api_smoke.py`, `test_api_runs.py` | Pipeline over REST, basis grouping/filter, policy results |
| **Total** | | **184** |

---

## Priority Queue — Next Work Items

### ✅ Done (2026-06-11) — Base MYGA pipeline

- ~~`core/projections/myga.py`~~ — Two-layer engine (decrements + AV roll-forward). 12 tests.
- ~~`core/discount.py`~~ — Zero curve with linear/cubic-spline interpolation, DF helpers. 17 tests.
- ~~`core/seriatim.py`~~ — MYGA routing live; Phase 2/3 products raise. 3 tests.
- ~~`standards/bel.py`~~ — Liability outflow discounting → ReserveResult. 7 tests incl. end-to-end.

Working pipeline: `MygaPolicyState` → `seriatim.calculate` → `GrossCashFlows` → `bel.calculate` → `ReserveResult`.

---

### ✅ Done (2026-06-11) — STAT CARVM

- ~~`standards/stat_carvm.py`~~ — Greatest-PV-of-guaranteed-benefits engine with CSV floor.
  13 closed-form tests. Added `valuation_interest_rate` to `StatCarvmConfig`
  (ASSUMPTION REQUIRED: SVL dynamic valuation rate). Simplifications: elective
  benefits only (no AG33 mortality-weighted streams), no free-withdrawal
  corridor election, no Reg 126 CFT overlay.

### ✅ Done (2026-07-14) — Aggregation, VM-22, Phase 1 reinsurance, RBC, REST

- ~~`core/aggregation.py`~~ — Cohort → segment → legal-entity rollup, partitioned by
  framework. 5 tests.
- ~~`standards/stat_vm22.py`~~ — DR (best-estimate outflows on the valuation curve) +
  SR (CTE65/70/80 over a placeholder parallel-rate-shock scenario set standing in for
  the NAIC generator); DR-only or max(DR, SR) per config. 9 tests.
- ~~`reinsurance/quota_share.py`~~ — Proportional ceded/retained split. 6 tests.
- ~~`reinsurance/application.py`~~ — Policy → treaty routing via
  `reinsurance_treaty_id`; ceded BEL / VM-22 wired (net = gross − ceded). 4 tests.
- ~~`capital/rbc.py`~~ — Factor-based C-1…C-4 → covariance → ACL RBC; RBC ratio when
  Total Adjusted Capital is supplied (ASSUMPTION REQUIRED: replace approximate
  factors with published NAIC tables). 7 tests.
- ~~`api/routes/runs.py` + `api/routes/results.py`~~ — POST /runs executes
  seriatim → reinsurance → BEL/CARVM/VM-22 → aggregation → RBC and persists to a
  DuckDB store (`api/store.py`, `AKIRA_DB_PATH`, in-memory default); GET
  /runs, /runs/{id}, /results, /results/{run_id} query it back. 5 tests.

Working pipeline (also live over REST): policies + treaties + curve →
`GrossCashFlows` → ceded/net → reserves per framework → rollup → ACL RBC.

---

### ✅ Done (2026-07-14) — LDTI, FAS 157, EBS, asset modules

- ~~`standards/ldti.py`~~ — LFPB (single-premium NPR mechanics: no future
  premiums, so LFPB = PV of benefits at the single-A curve; NPR reported and
  capped for disclosure) + straight-line DAC over the guarantee term via new
  `LdtiConfig.acquisition_cost_pct`. EGP basis raises. 9 tests.
- ~~`standards/fas157.py`~~ — Fair value = base PV (discount-basis spread over
  the supplied curve) + cost-of-capital risk margin (capital-ratio × duration
  proxy) + own-credit / prescribed non-performance relief. CALM / EXPLICIT
  margins raise. 7 tests.
- ~~`standards/ebs.py`~~ — Technical provisions = EBS BEL (risk-free +
  illiquidity premium) + CoC risk margin; BMA haircut applied to the ceded
  credit. SBA raises. 7 tests.
- ~~`assets/ledger.py`~~ — DuckDB upsert + read-back. 4 tests.
- ~~`assets/valuation.py`~~ — per-framework carrying values (STAT book with
  non-admitted at zero, LDTI HTM at amortized cost, FV/BEL at market, EBS
  post-haircut). 6 tests.
- API: POST /runs now executes all six reserve frameworks; LDTI DAC and EBS
  risk margin are persisted/returned as supplementary rows but excluded from
  the reserve aggregation.

All six Phase 1 reserve frameworks are now live end-to-end.

---

### ✅ Done (2026-09-24) — gaspatchio rewire & basis demarcation

- Projection engine rebuilt on gaspatchio (`engine/`): vectorised MYGA
  ActuarialFrame model replacing the per-policy / per-period loop engines
  (mortality, lapse, withdrawal, crediting calculators removed). Reconciled
  to a scalar reference at 1e-12. ~100x faster: 10k policies × all four
  bases in ~5s, vs ~60ms per policy for the old projection alone.
- Results demarcated into **STAT · US GAAP · LDTI · EBS** (`bases/`): basis
  stamped on every result, per-basis assumption blocks, per-basis
  aggregation, RBC restricted to STAT reserves.
- Methodology fixes (see ARCHITECTURE.md §4): valuation-date projection
  start, monthly crediting formula, lapse policy-year indexing, withdrawal
  timing (AV roll-forward now balances exactly).
- Per-policy results persisted (`policy_results`) and exposed over REST.
- Python 3.12 (gaspatchio requirement); pandas / scipy dropped.

---

### Priority 1 — Phase 2 kickoff (after MYGA validation)

**1. Product engines: `engine/projections/fia.py`, `engine/projections/spia.py` (gaspatchio models)**

**2. Phase 2 reinsurance: coinsurance, ModCo, funds withheld, YRT, XL**

**3. API assumptions / data routers** — CRUD for assumption sets, seriatim,
assets (wire `assets/ledger.py` in), treaties; feed real asset lists and TAC
into the RBC step.

---

### Known Phase 1 simplifications (revisit before production)

- MVA is hard-zero in the MYGA engine (no interest-rate path yet).
- Surrender schedules resolve from the embedded Athene repository; unknown IDs mean no charges.
- Joint-life decrements were removed with the loop engine. Re-implement in gaspatchio for SPIA / PRT.
- VM-22 SR re-discounts the fixed cash flows per rate scenario; cash flows are not re-projected per path.
- Quota share does not model ceding commission / expense allowance cash flows and ignores treaty effective / termination windows.
- CARVM ceded reserve stays 0 — statutory reinsurance reserve credit not yet applied.
- RBC factors are approximations of the NAIC Life tables (pre-tax); C-4 is reserve-proxied.
- FAS 157 / EBS risk margins use a cost-of-capital proxy (capital-ratio × duration); spreads and the illiquidity premium are placeholder constants. Policy-level values are pro-rata allocations.
- LDTI NPR is computed from the valuation-date projection, not locked at issue; cohort granularity is not applied; DAC needs real per-policy acquisition expenses.
- Asset valuation views return carrying values only — no amortization roll-forward or impairment logic.

---

### Phase 2 Backlog (after MYGA validation)

- Reinsurance: coinsurance, ModCo, funds withheld, YRT, XL
- Product engines: FIA, SPIA
- Frontend components (dashboard, results tables, scenario comparison charts)
- API: assumptions / data routers (CRUD for assumption sets, seriatim, assets, treaties)
- VM-22: real NAIC scenario generator + per-path cash-flow re-projection
- FAS 157 / EBS: projected-capital risk margins, published spread/IP tables
- EBS SBA approach; LDTI EGP basis; asset amortization roll-forward

### Phase 3 Backlog

- VA and ULSG projection engines
- `bases/ebs/ecr.py` — Bermuda ECR
- `capital/stochastic.py` — Stochastic capital

---

## Phase Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | MYGA + Quota Share; STAT / US GAAP / LDTI / EBS; NAIC RBC | ✅ Complete — gaspatchio engine, four demarcated bases, QS, RBC, REST (placeholder assumptions flagged `ASSUMPTION REQUIRED`) |
| **Phase 2** | PRT, SPIA, FIA; Coinsurance, ModCo, FWH, YRT, XL | 🔴 Not started |
| **Phase 3** | VA, ULSG; Bermuda ECR; stochastic capital | 🔴 Not started |

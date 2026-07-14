# AKIRA — Development Progress Tracker

*Last updated: 2026-07-14*

---

## Module Status

| Module | File(s) | Status | Tests | Notes |
|--------|---------|--------|-------|-------|
| **Mortality decrements** | `mortality/decrements.py` | ✅ Complete | 12 | SOA 2012 IAM + G2; single/joint life; monthly/quarterly/annual |
| **Mortality runner** | `mortality/runner.py` | ✅ Complete | (via integration) | Orchestrates a single-policy projection |
| **Lapse calculator** | `lapse/calculator.py` + `rates.py` | ✅ Complete | 14 | Rate tables, shock rates, annual→periodic conversion |
| **Withdrawal calculator** | `withdrawal/calculator.py` + `rates.py` | ✅ Complete | 38 | Surrender charges, free withdrawal, MVA |
| **Crediting calculator** | `crediting/calculator.py` | ✅ Complete | 16 | Fixed-rate; periodic conversion formula |
| **Assumption config** | `assumptions/sets.py` + `enums.py` + `validators.py` | ✅ Complete | Smoke | Full config framework; 20+ enums; cross-field validators |
| **Pydantic models** | `models/` (5 files) | ✅ Complete | Smoke | Policy, asset, reinsurance, results, cash flow structures |
| **FastAPI runs/results** | `api/main.py` + `api/routes/` + `api/store.py` | ✅ Complete | 5 | POST /runs executes the full pipeline; GET /runs, /results query the DuckDB store; assumptions/data routers still stubs |
| **MYGA projection** | `core/projections/myga.py` | ✅ Complete | 12 | Two-layer engine: decrements + AV roll-forward; ROAV/ROP, surrender charges, maturity |
| **Seriatim dispatcher** | `core/seriatim.py` | ✅ Complete | 3 | Routes MYGA policies; Phase 2/3 products raise NotImplementedError |
| **Aggregation** | `core/aggregation.py` | ✅ Complete | 5 | Cohort → segment → legal-entity rollup, framework-partitioned |
| **Discount / yield curve** | `core/discount.py` | ✅ Complete | 17 | Linear/cubic-spline zero curve, flat extrapolation, DF helpers |
| **Quota-share reinsurance** | `reinsurance/quota_share.py` | ✅ Complete | 6 | Proportional ceded/retained split of all monetary fields |
| **Reinsurance application** | `reinsurance/application.py` | ✅ Complete | 4 | Routes policy-treaty pairs via `reinsurance_treaty_id`; Phase 2 types raise |
| **Asset ledger** | `assets/ledger.py` | 🔴 Stub | — | Asset transaction journal |
| **Asset valuation** | `assets/valuation.py` | 🔴 Stub | — | Multi-framework asset views (BV, FV, statutory) |
| **BEL** | `standards/bel.py` | ✅ Complete | 8 | Discounts liability outflows at risk-free curve; ceded stream wired → net = gross − ceded |
| **STAT CARVM** | `standards/stat_carvm.py` | ✅ Complete | 13 | Greatest-PV of guaranteed benefits; CSV floor; closed-form tested |
| **VM-22** | `standards/stat_vm22.py` | ✅ Complete | 9 | DR + SR (CTE over placeholder rate-shock scenario set); DR-only / max(DR, SR) |
| **LDTI** | `standards/ldti.py` | 🔴 Stub | — | ASC 944 LFPB + DAC |
| **FAS 157** | `standards/fas157.py` | 🔴 Stub | — | ASC 820 fair-value liability |
| **EBS** | `standards/ebs.py` | 🔴 Stub | — | Bermuda Economic Balance Sheet |
| **NAIC RBC** | `capital/rbc.py` | ✅ Complete | 7 | Factor-based C-1…C-4, covariance, ACL; ratio when TAC supplied |
| **Bermuda ECR** | `capital/ecr.py` | 🔴 Stub | — | Enhanced Capital Requirement |
| **Stochastic capital** | `capital/stochastic.py` | 🔴 Stub | — | Scenario-driven stochastic capital |
| **Coinsurance** | `reinsurance/coinsurance.py` | 🔴 Phase 2 | — | |
| **ModCo** | `reinsurance/modco.py` | 🔴 Phase 2 | — | |
| **Funds Withheld** | `reinsurance/funds_withheld.py` | 🔴 Phase 2 | — | |
| **YRT** | `reinsurance/yrt.py` | 🔴 Phase 2 | — | |
| **Excess of Loss** | `reinsurance/excess_of_loss.py` | 🔴 Phase 2 | — | |
| **FIA projection** | `core/projections/fia.py` | 🔴 Phase 2 | — | |
| **SPIA projection** | `core/projections/spia.py` | 🔴 Phase 2 | — | |
| **VA projection** | `core/projections/va.py` | 🔴 Phase 3 | — | |
| **ULSG projection** | `core/projections/ulsg.py` | 🔴 Phase 3 | — | |
| **Frontend** | `frontend/src/` | 🔴 Stub | — | No components yet; scaffold (Vite + Tailwind + Recharts) only |

**Legend:** ✅ Implemented & tested &nbsp;|&nbsp; 🟡 Skeleton (calculation stub) &nbsp;|&nbsp; 🔴 Not started / stub only

---

## Test Coverage Summary

| Module | Test File | Count | Coverage |
|--------|-----------|-------|----------|
| Withdrawal | `test_withdrawal/test_withdrawal_rates.py` | 38 | Surrender schedules, free/partial withdrawal, MVA, integration |
| Crediting | `test_crediting/test_crediting.py` | 16 | FixedCreditingConfig, CreditorConfig, annual→periodic |
| Lapse | `test_lapse/test_lapse_rates.py` | 14 | LapseRateTable, repository, calculator, shock rates |
| Mortality | `test_mortality/test_decrements.py` | 12 | Single/joint life, lapse/withdrawal/crediting integration |
| Models | `test_models/` | Smoke | Schema validation only |
| Assumptions | `test_assumptions/` | Smoke | Schema validation only |
| API | `test_api_smoke.py` + `test_api_runs.py` | 6 | Health check + POST /runs pipeline, /results retrieval |
| Aggregation | `test_core/test_aggregation.py` | 5 | Grain rollups, framework partitioning |
| VM-22 | `test_standards/test_stat_vm22.py` | 9 | DR hand-calc, CTE tail, component selection, ceded |
| Quota share | `test_reinsurance/test_quota_share.py` | 6 | Split conservation, validation |
| Reinsurance application | `test_reinsurance/test_application.py` | 4 | Routing, retained fallback, Phase 2 guard |
| NAIC RBC | `test_capital/test_rbc.py` | 7 | Closed-form ACL, reserve-base preference, ratio |
| Remaining stubs | `test_core/` etc. | Stub | `NotImplementedError` guards (LDTI, FAS 157, EBS, ECR, Phase 2 reinsurance/products) |
| **Total** | | **203** | |

---

## Critical Path to First End-to-End MYGA Run

```
[Decrements — DONE]
  Mortality ✅  Lapse ✅  Withdrawal ✅  Crediting ✅
          │
          ▼
  MYGA Projection Engine  ◄── BLOCKER (core/projections/myga.py)
          │
          ├──► Discount / Yield Curve  (core/discount.py)
          │
          ▼
  Seriatim Dispatcher  (core/seriatim.py)
          │
          ├──► Quota-Share Reinsurance  (reinsurance/quota_share.py)
          │
          ▼
  Best Estimate Liability  (standards/bel.py)
          │
          ├──► STAT CARVM  (standards/stat_carvm.py)
          ├──► VM-22  (standards/stat_vm22.py)
          └──► [LDTI / FAS 157 / EBS — later]
                    │
                    ▼
             Aggregation  (core/aggregation.py)
                    │
                    ▼
              NAIC RBC  (capital/rbc.py)
                    │
                    ▼
               API Routes  (api/routes/)
```

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

### Priority 1 — Phase 2 kickoff (after MYGA validation)

**1. `standards/ldti.py` — ASC 944 LFPB + DAC**

**2. `standards/fas157.py` — Fair-value liability**

**3. `assets/ledger.py` + `assets/valuation.py`** — asset side of the balance sheet
(unblocks a real C-1 feed and TAC for the RBC ratio).

---

### Known Phase 1 simplifications (revisit before production)

- MVA is hard-zero in the MYGA engine (no interest-rate path yet).
- Projection basis is pinned to `stat_carvm` config; per-framework bases pending.
- Surrender schedules resolve from the embedded Athene repository; unknown IDs default to no charges.
- Decrement engine's `withdrawal_decrement` / `crediting_accrual` paths are bypassed by the MYGA engine (withdrawal modeled in AV layer; counts unaffected) — consider cleaning up the engine itself.
- VM-22 SR re-discounts the fixed best-estimate cash flows per rate scenario; cash flows are not re-projected per path (dynamic lapse / MVA interaction deferred until an interest-rate path reaches the MYGA engine).
- Quota share does not model ceding commission / expense allowance cash flows (no premium or expense fields on the MYGA record yet) and ignores treaty effective / termination windows.
- CARVM ceded reserve stays 0 — statutory reinsurance reserve credit (authorization / collateral rules) not yet applied.
- RBC factors are approximations of the NAIC Life tables (pre-tax); C-4 is reserve-proxied because premium income isn't carried in the model.

---

### Phase 2 Backlog (after MYGA validation)

- `standards/ebs.py` — Bermuda Economic Balance Sheet
- Reinsurance: coinsurance, ModCo, funds withheld, YRT, XL
- Product engines: FIA, SPIA
- Frontend components (dashboard, results tables, scenario comparison charts)
- API: assumptions / data routers (CRUD for assumption sets, seriatim, assets, treaties)
- VM-22: real NAIC scenario generator + per-path cash-flow re-projection

### Phase 3 Backlog

- VA and ULSG projection engines
- `capital/ecr.py` — Bermuda ECR
- `capital/stochastic.py` — Stochastic capital

---

## Phase Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | MYGA + Quota Share; all 6 reserve frameworks; NAIC RBC | 🔶 Nearly complete — BEL / CARVM / VM-22 / QS / RBC / REST live; LDTI, FAS 157, EBS remain |
| **Phase 2** | PRT, SPIA, FIA; Coinsurance, ModCo, FWH, YRT, XL | 🔴 Not started |
| **Phase 3** | VA, ULSG; Bermuda ECR; stochastic capital | 🔴 Not started |

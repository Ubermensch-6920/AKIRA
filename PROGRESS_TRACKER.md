# AKIRA — Development Progress Tracker

*Last updated: 2026-06-11*

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
| **FastAPI skeleton** | `api/main.py` + `api/routes/` | 🟡 Skeleton | 1 (health) | CORS + health check working; all route bodies are stubs |
| **MYGA projection** | `core/projections/myga.py` | ✅ Complete | 12 | Two-layer engine: decrements + AV roll-forward; ROAV/ROP, surrender charges, maturity |
| **Seriatim dispatcher** | `core/seriatim.py` | ✅ Complete | 3 | Routes MYGA policies; Phase 2/3 products raise NotImplementedError |
| **Aggregation** | `core/aggregation.py` | 🔴 Stub | — | Cohort → Segment → BalanceSheet rollup |
| **Discount / yield curve** | `core/discount.py` | ✅ Complete | 17 | Linear/cubic-spline zero curve, flat extrapolation, DF helpers |
| **Quota-share reinsurance** | `reinsurance/quota_share.py` | 🔴 Stub | — | Phase 1 reinsurance type; treaty model exists |
| **Reinsurance application** | `reinsurance/application.py` | 🔴 Stub | — | Routes policy-treaty pairs to reinsurance engines |
| **Asset ledger** | `assets/ledger.py` | 🔴 Stub | — | Asset transaction journal |
| **Asset valuation** | `assets/valuation.py` | 🔴 Stub | — | Multi-framework asset views (BV, FV, statutory) |
| **BEL** | `standards/bel.py` | ✅ Complete | 7 | Discounts liability outflows at risk-free curve; end-to-end pipeline tested |
| **STAT CARVM** | `standards/stat_carvm.py` | ✅ Complete | 13 | Greatest-PV of guaranteed benefits; CSV floor; closed-form tested |
| **VM-22** | `standards/stat_vm22.py` | 🔴 Stub | — | NAIC VM-22 deterministic + stochastic reserve |
| **LDTI** | `standards/ldti.py` | 🔴 Stub | — | ASC 944 LFPB + DAC |
| **FAS 157** | `standards/fas157.py` | 🔴 Stub | — | ASC 820 fair-value liability |
| **EBS** | `standards/ebs.py` | 🔴 Stub | — | Bermuda Economic Balance Sheet |
| **NAIC RBC** | `capital/rbc.py` | 🔴 Stub | — | Risk-Based Capital C-1 through C-4 |
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
| API | `test_api_smoke.py` | 1 | Health check |
| Core / Standards / Capital / Reinsurance | `test_core/` etc. | Stub | `NotImplementedError` guards only |
| **Total** | | **~111** | |

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

### Priority 1 — Aggregation & VM-22

**1. `core/aggregation.py` — Rollup**
- Aggregate policy-level results into cohort → segment → legal entity tables.
- Needed before API routes can return anything meaningful.

**2. `standards/stat_vm22.py` — VM-22 Reserve**
- Deterministic Reserve (DR) + Stochastic Reserve (SR).
- Required for NAIC statutory compliance target.

---

### Priority 2 — Phase 1 Reinsurance

**4. `reinsurance/quota_share.py`**
- Implement gross→ceded→net split. Treaty model (`ReinsuranceTreaty`) and `GrossCashFlows` structure both exist.
- Then wire ceded BEL into `standards/bel.py` (currently ceded = 0).

**5. `reinsurance/application.py`**
- Route each policy-treaty pair to its reinsurance engine; aggregate ceded/net results.

---

### Priority 3 — Capital & REST Exposure

**6. `capital/rbc.py` — NAIC RBC**
- C-1 (asset risk), C-2 (insurance risk), C-3 (interest rate risk), C-4 (business risk).
- C-2 and C-3 depend on MYGA projection output.

**7. `api/routes/runs.py` + `api/routes/results.py`**
- Wire `/runs` POST → seriatim → aggregation pipeline.
- Wire `/results` GET → DuckDB query of persisted run output.

---

### Known Phase 1 simplifications (revisit before production)

- MVA is hard-zero in the MYGA engine (no interest-rate path yet).
- Projection basis is pinned to `stat_carvm` config; per-framework bases pending.
- Surrender schedules resolve from the embedded Athene repository; unknown IDs default to no charges.
- Decrement engine's `withdrawal_decrement` / `crediting_accrual` paths are bypassed by the MYGA engine (withdrawal modeled in AV layer; counts unaffected) — consider cleaning up the engine itself.

---

### Phase 2 Backlog (after MYGA validation)

- `standards/ldti.py` — ASC 944 LFPB + DAC
- `standards/fas157.py` — Fair-value liability
- `assets/ledger.py` + `assets/valuation.py` — Asset side of balance sheet
- Reinsurance: coinsurance, ModCo, funds withheld, YRT, XL
- Product engines: FIA, SPIA
- Frontend components (dashboard, results tables, scenario comparison charts)

### Phase 3 Backlog

- VA and ULSG projection engines
- `capital/ecr.py` — Bermuda ECR
- `capital/stochastic.py` — Stochastic capital

---

## Phase Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | MYGA + Quota Share; all 6 reserve frameworks; NAIC RBC | 🔶 In progress — decrements done, projection engine next |
| **Phase 2** | PRT, SPIA, FIA; Coinsurance, ModCo, FWH, YRT, XL | 🔴 Not started |
| **Phase 3** | VA, ULSG; Bermuda ECR; stochastic capital | 🔴 Not started |

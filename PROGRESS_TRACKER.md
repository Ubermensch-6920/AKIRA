# AKIRA — Development Progress Tracker

*Last updated: 2026-06-05*

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
| **MYGA projection** | `core/projections/myga.py` | 🔴 Stub | — | **Critical path blocker — everything downstream depends on this** |
| **Seriatim dispatcher** | `core/seriatim.py` | 🔴 Stub | — | Routes a policy input to a product engine |
| **Aggregation** | `core/aggregation.py` | 🔴 Stub | — | Cohort → Segment → BalanceSheet rollup |
| **Discount / yield curve** | `core/discount.py` | 🔴 Stub | — | Discount factor vectors; required by BEL + all frameworks |
| **Quota-share reinsurance** | `reinsurance/quota_share.py` | 🔴 Stub | — | Phase 1 reinsurance type; treaty model exists |
| **Reinsurance application** | `reinsurance/application.py` | 🔴 Stub | — | Routes policy-treaty pairs to reinsurance engines |
| **Asset ledger** | `assets/ledger.py` | 🔴 Stub | — | Asset transaction journal |
| **Asset valuation** | `assets/valuation.py` | 🔴 Stub | — | Multi-framework asset views (BV, FV, statutory) |
| **BEL** | `standards/bel.py` | 🔴 Stub | — | Best Estimate Liability; cross-cuts all frameworks |
| **STAT CARVM** | `standards/stat_carvm.py` | 🔴 Stub | — | Pre-VM-22 statutory reserve |
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

### Priority 1 — Unblock the Projection Engine

**1. `core/projections/myga.py` — MYGA Cash Flow Projection Loop**
- The single most critical blocker. All decrements exist; this wires them into a time-stepped accumulation of account value, interest, cash flows, and benefits.
- Key inputs: `MygaPolicyState`, `AssumptionSet`
- Key outputs: `GrossCashFlows` (populated `pd.DataFrame` indexed by projection date)
- Pattern to follow: `mortality/runner.py` for the projection loop skeleton

**2. `core/discount.py` — Yield Curve & Discount Factors**
- Build a discount factor vector from a flat rate or a curve (term-structure).
- Required by BEL and every reserve framework.
- Simple first pass: flat-rate spot curve → discount factors as `np.ndarray`

---

### Priority 2 — Orchestration

**3. `core/seriatim.py` — Policy Dispatcher**
- Route a `SeriatimPolicyInput` to the correct product engine, return `GrossCashFlows`.
- Phase 1: only MYGA branch needs to be live.

**4. `core/aggregation.py` — Rollup**
- Aggregate policy-level results into cohort → segment → legal entity tables.
- Needed before API routes can return anything meaningful.

---

### Priority 3 — First Reserve Frameworks

**5. `standards/bel.py` — Best Estimate Liability**
- Discount `GrossCashFlows` using the yield curve to produce a scalar BEL per policy.
- Cross-cuts all six frameworks; implement once, reuse everywhere.

**6. `standards/stat_carvm.py` — Pre-VM-22 CARVM**
- Simplest statutory reserve; good validation baseline against hand-calculated numbers.
- Uses BEL + lapse-supported reserve adjustment.

**7. `standards/stat_vm22.py` — VM-22 Reserve**
- Deterministic Reserve (DR) + Stochastic Reserve (SR).
- Required for NAIC statutory compliance target.

---

### Priority 4 — Phase 1 Reinsurance

**8. `reinsurance/quota_share.py`**
- Implement gross→ceded→net split. Treaty model (`ReinsuranceTreaty`) and `GrossCashFlows` structure both exist.

**9. `reinsurance/application.py`**
- Route each policy-treaty pair to its reinsurance engine; aggregate ceded/net results.

---

### Priority 5 — Capital & REST Exposure

**10. `capital/rbc.py` — NAIC RBC**
- C-1 (asset risk), C-2 (insurance risk), C-3 (interest rate risk), C-4 (business risk).
- C-2 and C-3 depend on MYGA projection output.

**11. `api/routes/runs.py` + `api/routes/results.py`**
- Wire `/runs` POST → seriatim → aggregation pipeline.
- Wire `/results` GET → DuckDB query of persisted run output.

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

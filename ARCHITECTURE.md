# AKIRA Architecture & Data Flow

AKIRA is a multi-basis actuarial reserving and capital model. Cash flows are
projected by a vectorised [gaspatchio](https://gaspatchio.dev/latest/) model,
and every result is **demarcated by accounting / regulatory basis**:

| Basis       | Package                  | Frameworks / measures                                   | Assumption block          | Discount curve                         |
|-------------|--------------------------|---------------------------------------------------------|---------------------------|----------------------------------------|
| **STAT**    | `bases/stat/`            | CARVM (Pre-VM-22), VM-22 (DR + SR), NAIC RBC            | `assumption_set.stat`     | statutory valuation rate / VM-22 curve |
| **US GAAP** | `bases/us_gaap/`         | ASC 820 fair value (FAS 157)                            | `assumption_set.us_gaap`  | curve + discount-basis spread          |
| **LDTI**    | `bases/ldti/`            | ASC 944 LFPB, DAC (supplementary asset)                 | `assumption_set.ldti`     | upper-medium-grade (single-A)          |
| **EBS**     | `bases/ebs/`             | BEL, technical provisions (+ risk margin), ECR (stub)    | `assumption_set.ebs`      | risk-free (+ illiquidity premium)      |

Rules the code enforces:

1. **Every result is stamped with its basis.** `ResultMetadata.basis` is derived
   from the framework (`Framework.basis`), so it can't be mislabelled.
2. **Each basis projects on its own assumptions.** Every framework config
   inherits `ProjectionBasisConfig` (mortality, lapse, withdrawal, crediting).
   A prudent STAT VM-22 block and a best-estimate EBS block produce different
   projections. Identical blocks share one gaspatchio run.
3. **Results from different bases never sum.** Aggregation groups by
   (basis, framework) first. RBC reads STAT reserves only (VM-22, falling back
   to CARVM). Other bases' reserves are ignored, never summed in.
4. **Supplementary measures stay out of roll-ups.** LDTI DAC (an asset) and the
   EBS risk margin (already inside the technical provisions) are reported but
   not aggregated.

---

## 1. Module Structure

```
src/actuarial_model/
├── pipeline.py              # run_valuation(): project → reinsure → bases → aggregate
│
├── assumptions/             # configuration + rate-table data (no calculation)
│   ├── enums.py             # Basis, Framework (→ basis), every lever as an Enum
│   ├── sets.py              # AssumptionSet = stat | us_gaap | ldti | ebs | reinsurance
│   ├── validators.py        # cross-basis consistency checks
│   ├── mortality.py         # SOA 2012 IAM + G2 embedded tables, repository
│   ├── lapse.py             # LapseRateTable (base + shock years)
│   └── withdrawal.py        # surrender schedules, partial withdrawal, MVA config
│
├── engine/                  # shared projection engine (gaspatchio)
│   ├── grid.py              # ProjectionGrid: monthly, anchored at the valuation date
│   ├── curves.py            # CurvePoint → gaspatchio Curve; shifts, floors, DFs
│   ├── tables.py            # config → content-addressed gaspatchio Tables
│   ├── model_points.py      # seriatim records → model-point frame (timing resolved)
│   ├── projection.py        # Projection: one row per policy, list column per cash flow
│   ├── seriatim.py          # product dispatcher
│   ├── aggregation.py       # per-policy → cohort / segment / legal entity (polars)
│   └── projections/
│       ├── myga.py          # MYGA gaspatchio model (Phase 1)
│       └── fia.py, spia.py, va.py, ulsg.py   # Phase 2/3 stubs
│
├── reinsurance/             # gross → ceded / net on projection frames
│   ├── application.py       # per-policy treaty share, one vectorised split
│   ├── quota_share.py       # Phase 1
│   └── coinsurance.py, modco.py, funds_withheld.py, yrt.py,
│       excess_of_loss.py, risk_transfer.py   # Phase 2 stubs
│
├── bases/                   # ← the demarcation
│   ├── common.py            # RunStamp, MeasureResult, BasisResult, PV / duration helpers
│   ├── context.py           # ValuationContext: inputs + per-block projection cache
│   ├── stat/                # carvm.py (gaspatchio greatest-PV), vm22.py, rbc.py
│   ├── us_gaap/             # fair_value.py (ASC 820)
│   ├── ldti/                # lfpb.py, dac.py
│   └── ebs/                 # bel.py, technical_provisions.py, ecr.py (stub)
│
├── capital/stochastic.py    # cross-basis stochastic capital (stub)
├── assets/                  # DuckDB asset ledger + per-basis carrying values
├── models/                  # Pydantic records: policy, asset, treaty, results, runs
└── api/                     # FastAPI: /runs, /results (basis filter), /results/{id}/policies
```

---

## 2. Data Flow

```
 MygaPolicyState[]  ──►  engine.model_points  ──►  model-point frame (1 row / policy)
                                                        │
      for each distinct ProjectionBasisConfig block     │  (bases.context cache)
                                                        ▼
                                   engine.projections.myga  (gaspatchio ActuarialFrame)
                                   time → mortality → lapse → withdrawals →
                                   account value → in force → cash flows
                                                        │
                                                        ▼
                                   Projection (list[f64] per cash-flow line)
                                                        │
                                   reinsurance.application  → gross / ceded / net
                                                        │
       ┌───────────────────────┬────────────────────────┼───────────────────────┐
       ▼                       ▼                        ▼                       ▼
     STAT                   US GAAP                   LDTI                    EBS
  CARVM (guaranteed,     ASC 820 FV =             LFPB = PV @ single-A     BEL @ risk-free
   own gaspatchio        base PV + CoC RM         NPR (capped, disclosed)  TP = BEL @ rf+IP
   greatest-PV frame)    + own-credit adj         DAC straight-line        + CoC risk margin
  VM-22 DR + CTE SR                                (supplementary)          (RM supplementary)
  NAIC RBC (STAT only)
       │                       │                        │                       │
       └───────────────────────┴──────────┬─────────────┴───────────────────────┘
                                          ▼
                        MeasureResult = ReserveResult (run total)
                                      + per-policy detail frame
                                          │
                                          ▼
                     engine.aggregation (basis, framework) × cohort / segment / entity
                                          │
                                          ▼
                    api.store (DuckDB): runs · results (basis-tagged) · policy_results
```

### Why the projection carrier is a frame

The old engine produced one Pydantic record per policy per month and looped
over them for every framework. The `Projection` carrier is a polars frame with
one row per policy and one `list[f64]` column per cash-flow line on a shared
monthly grid. That makes every downstream step whole-column arithmetic:

- **Reinsurance**: `ceded = gross × share` for all policies and periods at once.
- **Present value**: `PV_i = Σ_t outflow_i(t) · DF(tenor_t)`, with the DF
  vector computed once per curve.
- **Aggregation**: a polars `group_by` over the stacked per-policy details.

---

## 3. The MYGA gaspatchio model

`engine/projections/myga.py::build_frame` builds the model as named
gaspatchio columns (use `project(..., detail=True)` to keep the diagnostics):

| Section        | Columns                                                                           |
|----------------|-----------------------------------------------------------------------------------|
| Time           | `t`, `duration_months`, `policy_year`, `attained_age`                              |
| Mortality      | `base_qx`, `g2_rate`, `annual_qx`, `monthly_qx` (constant force)                  |
| Lapse          | `annual_lapse_rate` (policy-year table, shocks), `monthly_lapse_rate`             |
| Withdrawals    | `withdrawal_rate` = free % × monthly partial-withdrawal incidence                 |
| Account value  | `av_bop_pp`, `av_mid_pp` (+ interest), `av_eop_pp` (− withdrawals)               |
| In force       | `survival`, `in_force_bop` (masked after maturity), `deaths`, `surrenders`, `survivors` |
| Cash flows     | `interest_credited`, `death_benefits`, `surrender_benefits`, `surrender_charge`, `partial_withdrawals`, `maturity_benefits`, `account_value_eop`, `lives_in_force` |

The account-value roll-forward balances exactly (tested to 1e-10):
`AV_bop + interest = death + surrender + charge + withdrawals + maturity + AV_eop`.
The model is also reconciled to a scalar month-by-month reference
(`tests/test_engine/test_myga_projection.py`) at 1e-12 relative.

**gaspatchio traps handled in the engine**

- *Scalar vs. vector columns.* A per-policy scalar column is not a projection
  vector: `cum_prod()` on it runs down the *rows* (across policies). Grid
  vectors are attached with `engine.grid.grid_vector`, and everything
  time-varying is derived from them.
- *Global table registry.* gaspatchio resolves `Table.lookup` by name at
  execution time, and re-registering a name with different data supersedes the
  old table. `engine.tables` names every table by a hash of its contents, so two
  bases with different lapse tables can never read each other's rates.
- *Logging.* gaspatchio logs through loguru at DEBUG. `engine/__init__.py`
  disables the `gaspatchio` logger so AKIRA's own `logging` config governs output.

---

## 4. Methodology changes in the rewire

These are deliberate fixes, not refactoring noise. Each is pinned by a test.

| Area | Before (loop engine) | Now (gaspatchio) |
|------|----------------------|------------------|
| Projection start | From **issue date**, with pre-valuation periods dropped. In-force policies started from their current AV at issue, so decrements and ageing were double-counted | From the **valuation date**, with current AV and in force = 1. Durations are measured from issue |
| Monthly crediting | `1 − (1 − i)^(1/12)`, which over-credits (3% → ~3.09% p.a.) | `(1 + i)^(1/12) − 1` |
| Lapse policy year | `ceil((period − 1) / 12)`, so shock years started one month late | `duration_months // 12 + 1` |
| Partial withdrawals | Taken by all BOP in force, so deaths and surrenders got the withdrawal *and* full AV | Taken by survivors. Maturity pays post-withdrawal AV, and the AV roll-forward balances |
| Projection basis | Every framework projected on the `stat_carvm` block | Each framework projects on its own block (identical blocks share one run) |
| RBC reserve base | Fell back to *any* reserve supplied ("MIXED") | STAT reserves only |
| BEL asset view | Market value (grouped with FAS 157) | EBS view (`market_value_ebs`), since BEL reports under EBS |
| Curve interpolation | LINEAR / CUBIC_SPLINE (scipy) | LINEAR / LOG_LINEAR / PCHIP (gaspatchio `Curve`) |
| Joint-life decrements | Implemented in the (unused-by-MYGA) loop engine | Removed with the loop engine. Re-add in gaspatchio with SPIA/PRT (Phase 2) |

Non-additive measures (VM-22 CTE, CoC risk margins, fair value) are computed
at portfolio level, then allocated to policies pro rata to their additive
driver (DR, EBS BEL, base PV). The allocation is recorded in
`components["allocation"]`.

---

## 5. Running

```python
from actuarial_model.pipeline import run_valuation
from actuarial_model.assumptions import AssumptionSet, Framework, Basis

output = run_valuation(
    assumption_set=aset,              # aset.stat / .us_gaap / .ldti / .ebs blocks
    valuation_date=val_date,
    policies=policies,                # list[MygaPolicyState]
    curve_points=curve,               # list[CurvePoint]
    frameworks=list(Framework),
    treaties=treaties,
)
output.bases[Basis.STAT].reserve_results()   # CARVM, VM-22
output.bases[Basis.STAT].capital             # NAIC RBC
output.policy_results()                      # polars: basis, framework, policy, gross/ceded/net
output.aggregation.by_segment
```

Single-policy debugging: `engine.projections.myga.project([policy], config,
val_date, detail=True).frame` returns every intermediate vector.

REST: `POST /runs` returns `bases: {STAT, US_GAAP, LDTI, EBS}` plus the flat
lists. `GET /results?basis=EBS` filters by basis.
`GET /results/{run_id}/policies?basis=STAT` returns per-policy results.

---

## 6. Test map

| Area | File |
|------|------|
| Engine vs scalar reference, AV balance, timing, maturity, ROP | `tests/test_engine/test_myga_projection.py` |
| Curves (gaspatchio) | `tests/test_engine/test_curves.py` |
| Grid, model points, content-addressed tables | `tests/test_engine/test_tables_and_grid.py` |
| Seriatim, aggregation | `tests/test_engine/test_seriatim.py`, `test_aggregation.py` |
| Reinsurance on frames | `tests/test_reinsurance/test_reinsurance.py` |
| STAT CARVM closed forms | `tests/test_bases/test_stat_carvm.py` |
| VM-22, FAS 157, LDTI, BEL, EBS hand calcs | `tests/test_bases/test_best_estimate_bases.py` |
| NAIC RBC (STAT-only base) | `tests/test_bases/test_stat_rbc.py` |
| Basis demarcation (pipeline) | `tests/test_bases/test_demarcation.py` |
| REST | `tests/test_api_runs.py` |

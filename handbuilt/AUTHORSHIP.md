# Authorship log

AKIRA is built with AI assistance. This log records who wrote what, so the
split is verifiable.

**Legend:** ✍️ hand-written by me · 🤝 written by me, reviewed with AI ·
🤖 AI-generated, reviewed by me

## Hand-built engine (`handbuilt/akira_handbuilt/`)

| Component | File / function | Author | Date | Commit | Notes |
|-----------|-----------------|--------|------|--------|-------|
| Step 1 — time grid | `myga.duration_and_policy_year`, `attained_age` | | | | |
| Step 2 — rate conversions | `myga.annual_to_monthly_decrement`, `monthly_credit_rate` | | | | |
| Step 3 — policy-year lookup | `myga.rate_by_policy_year` | | | | |
| Step 4 — mortality | `myga.adjusted_annual_qx` | | | | |
| Step 5 — in force | `myga.in_force` | | | | |
| Step 6 — account value | `myga.account_value_per_policy` | | | | |
| Step 7 — cash flows | `myga.cash_flows` | | | | |
| Wiring | `myga.project` | 🤖 | 2026-10-02 | | Calls steps 1-7 in order |
| Data plumbing | `inputs.py` | 🤖 | 2026-10-02 | | Model points → arrays, table lookups, frame assembly |
| Tests (spec) | `handbuilt/test_hb/` | 🤖 | 2026-10-02 | | Hand-calculated expectations, reviewed by me |

## Everything else (as of 2026-10-02)

| Area | Author | Notes |
|------|--------|-------|
| gaspatchio benchmark engine, bases, pipeline, API | 🤖 | PR #12; methodology decisions reviewed by me |
| Phase 1 modules before PR #12 | 🤖 / 🤝 | See git history |

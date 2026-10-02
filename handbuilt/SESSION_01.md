# Session 01 — Hand-built MYGA engine, steps 1-6 (2 hours)

**Goal:** write the NumPy projection core yourself, function by function,
until each step's test passes. Next session finishes the cash flows (step 7)
and reconciles the whole engine to the gaspatchio benchmark.

**Your file:** `handbuilt/akira_handbuilt/myga.py`
**Your tests:** `handbuilt/test_hb/test_myga_handbuilt.py`

```bash
source .venv/bin/activate          # or: python3.12 -m venv .venv && pip install -e ".[dev]"
pytest handbuilt -rs               # SKIPPED "TODO ..." = not built yet; PASSED = done
pytest handbuilt -k step3 -rs      # run one step's tests
```

## Rules for yourself

- Write the function bodies by hand. Use AI to **explain** a concept or a
  NumPy function, or to **review** code you've written. Don't ask it for the body.
- Before coding each step, write the formula on paper for a 2-policy x 3-month
  example, then check your output against it.
- Commit after every green step, under your own name, with the actuarial
  reasoning in the message, for example:
  `Step 5: in-force via cumulative survival; zeroed after maturity period`
- Log each step in `AUTHORSHIP.md` once its test passes.

## Plan

| Time        | Step | Function(s)                                      | What you'll learn |
|-------------|------|--------------------------------------------------|-------------------|
| 0:00 – 0:10 | 0    | Setup; read `project()` at the bottom of the file | How the steps chain together |
| 0:10 – 0:25 | 1    | `duration_and_policy_year`, `attained_age`        | Broadcasting `(P,1)` against `(1,T)` |
| 0:25 – 0:35 | 2    | `annual_to_monthly_decrement`, `monthly_credit_rate` | Decrement vs. interest compounding |
| 0:35 – 0:55 | 3    | `rate_by_policy_year`                             | Boolean-mask lookups |
| 0:55 – 1:15 | 4    | `adjusted_annual_qx`                              | Mortality improvement, broadcasting a `(T,)` vector |
| 1:15 – 1:45 | 5    | `in_force`                                        | Survivorship as a shifted cumulative product; masking at maturity |
| 1:45 – 2:00 | 6    | `account_value_per_policy`                        | The same pattern, applied to money |

If you run over, stop after step 5: it's the important one. Step 6 reuses its pattern.

## Hints (read only when stuck for 10+ minutes)

<details><summary>Step 1</summary>

`duration_months_at_valuation[:, None]` has shape `(P, 1)` and `np.arange(n)[None, :]`
has shape `(1, T)`. Adding them broadcasts to `(P, T)`. Integer `//` works element-wise.
For the age clip, look at `np.clip`.
</details>

<details><summary>Step 2</summary>

Both are one line. Wrap the input in `np.asarray(..., dtype=float)` so a plain
float works too. Sanity check: twelve monthly survivals multiply back to the annual one.
</details>

<details><summary>Step 3</summary>

Start from `np.full(policy_year.shape, default_rate)`, then overwrite cells
where `policy_year == year` for each override. A dict usually has only a few
keys, so a loop over the dict is fine; a loop over cells is not.
</details>

<details><summary>Step 4</summary>

`years_since_g2_base` is `(T,)`. NumPy broadcasts it across rows automatically
against `(P, T)` arrays. Finish with `np.clip(..., 0.0, 1.0)`.
</details>

<details><summary>Step 5</summary>

`np.cumprod(survival, axis=1)` gives end-of-period survival. BOP in force is that
shifted right by one, with 1.0 in column 0: create `np.ones_like(survival)` and
fill `[:, 1:]`. For the maturity mask, compare `np.arange(T)[None, :]` with
`maturity_period[:, None]`.
</details>

<details><summary>Step 6</summary>

The growth factor per month is `(1 + i) * (1 - w)`. AV at BOP is
`account_value` times the shifted cumulative product of that factor, the same
trick as step 5.
</details>

## Done when

- `pytest handbuilt -rs` shows steps 1-6 PASSED. Step 7 and the
  reconciliation test still show TODO.
- `pytest` (the whole suite) is still green.
- There are six commits, one per step, and `AUTHORSHIP.md` is updated.

## Next session

Step 7 `cash_flows`: the formulas are in its docstring. Then
`test_reconciles_to_gaspatchio` should pass. When it does, move the engine
into `src/actuarial_model/engine/` and point `engine/seriatim.py` at it. Every
basis (STAT, US GAAP, LDTI, EBS) then runs on your engine.

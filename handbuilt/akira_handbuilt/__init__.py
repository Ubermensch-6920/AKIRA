"""
Hand-built NumPy projection engine.

Lives outside ``src/`` while it's being written; it moves into
``actuarial_model.engine`` once it reconciles to the benchmark.

Authorship split (see ``handbuilt/AUTHORSHIP.md``):
  - ``myga.py``   actuarial calculation functions — written by hand.
  - ``inputs.py`` data plumbing (model points → arrays, table lookups,
                  frame assembly) — AI-assisted.

Every array is shaped ``(P, T)``: P policies (rows) x T monthly periods
(columns) on the shared valuation-date grid. The gaspatchio model in
``engine/projections/myga.py`` stays in place as the benchmark this engine
must reconcile to.
"""

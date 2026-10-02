"""
Hand-built NumPy projection engine.

Authorship split (see ``docs/handbuilt/AUTHORSHIP.md``):
  - ``myga.py``   actuarial calculation functions — written by hand.
  - ``inputs.py`` data plumbing (model points → arrays, table lookups,
                  frame assembly) — AI-assisted.

Every array is shaped ``(P, T)``: P policies (rows) x T monthly periods
(columns) on the shared valuation-date grid. The gaspatchio model in
``engine/projections/myga.py`` stays in place as the benchmark this engine
must reconcile to.
"""

# handbuilt/ — my NumPy engine workspace

Kept separate from `src/actuarial_model/` while I write it. Nothing in the
main package imports from here. Once the engine reconciles to the gaspatchio
benchmark, it moves into `src/actuarial_model/engine/`.

```
handbuilt/
├── akira_handbuilt/
│   ├── myga.py      # ✍️ my calculation functions (steps 1-7) + provided wiring
│   └── inputs.py    # 🤖 data plumbing (arrays in, Projection frame out)
├── test_hb/         # per-step hand-calculated tests + reconciliation to gaspatchio
├── SESSION_01.md    # today's plan
└── AUTHORSHIP.md    # who wrote what
```

```bash
pytest handbuilt -rs     # SKIPPED "TODO Step N" = not written yet
```

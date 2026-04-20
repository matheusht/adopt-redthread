# Scripts

This folder will hold small MVP entrypoints.

Current scripts:
- `ingest_zapi.py` — normalize ZAPI discovery output
- `ingest_adopt_actions.py` — normalize an Adopt action catalog into fixtures
- `generate_replay_pack.py` — turn normalized fixtures into replay-pack groups
- `prepublish_gate.py` — prototype gate for approve/review/block decisions

Handy commands:
- `make test` — run the local test suite
- `make demo-zapi` — regenerate the sample ZAPI fixture bundle
- `make demo-adopt-actions` — regenerate the sample action fixture bundle
- `make demo-gate` — regenerate the replay plan and gate verdict
- `make demo-all` — run the full local demo flow

Later scripts:
- `classify_risk.py` — split-out classifier if the heuristics outgrow the loader

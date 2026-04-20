# Scripts

This folder will hold small MVP entrypoints.

Current scripts:
- `ingest_zapi.py` — normalize ZAPI discovery output
- `generate_replay_pack.py` — turn normalized fixtures into replay-pack groups

Later scripts:
- `classify_risk.py` — split-out classifier if the heuristics outgrow the loader
- `prepublish_gate.py` — gate draft/publish with replay evidence

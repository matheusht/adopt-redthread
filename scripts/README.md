# Scripts

This folder will hold small MVP entrypoints.

Current scripts:
- `ingest_zapi.py` — normalize ZAPI discovery output or HAR-derived captures
- `ingest_adopt_actions.py` — normalize an Adopt action catalog into fixtures
- `generate_replay_pack.py` — turn normalized fixtures into replay-pack groups
- `prepublish_gate.py` — prototype gate for approve/review/block decisions

Handy commands:
- `make test` — run the local test suite
- `make demo-zapi` — regenerate the sample catalog-style ZAPI fixture bundle
- `make demo-zapi-har` — regenerate the sample HAR-derived fixture bundle, replay plan, and gate verdict
- `make demo-adopt-actions` — regenerate the sample action fixture bundle
- `make demo-gate` — regenerate the replay plan and gate verdict for the catalog-style sample
- `make demo-all` — run the original local demo flow

## HAR notes

The HAR lane is meant for local bridge work against real captures.

Recommended flow:

```bash
python3 scripts/ingest_zapi.py /path/to/demo_session_filtered.har /path/to/output_fixture_bundle.json
python3 scripts/generate_replay_pack.py /path/to/output_fixture_bundle.json /path/to/output_replay_plan.json
python3 scripts/prepublish_gate.py /path/to/output_replay_plan.json /path/to/output_gate_verdict.json
```

Safety rule:
- keep raw `.har` files out of git
- commit normalized fixture bundles only after checking that sensitive values are gone

Later scripts:
- `classify_risk.py` — split-out classifier if the heuristics outgrow the loader

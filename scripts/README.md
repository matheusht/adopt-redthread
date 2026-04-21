# Scripts

This folder will hold small MVP entrypoints.

Current scripts:
- `ingest_zapi.py` — normalize ZAPI discovery output or HAR-derived captures
- `ingest_noui.py` — normalize a NoUI MCP server output into fixtures
- `ingest_adopt_actions.py` — normalize an Adopt action catalog into fixtures
- `generate_replay_pack.py` — turn normalized fixtures into replay-pack groups
- `prepublish_gate.py` — prototype gate for approve/review/block decisions
- `export_redthread_runtime_inputs.py` — convert normalized fixture bundles into real RedThread replay and dry-run campaign input shapes
- `evaluate_redthread_replay.py` — evaluate exported replay traces with RedThread's actual promotion-gate code
- `run_redthread_dryrun.py` — run one exported case through a real RedThread dry-run campaign path

Handy commands:
- `make test` — run the local test suite
- `make demo-zapi` — regenerate the sample catalog-style ZAPI fixture bundle
- `make demo-zapi-har` — regenerate the sample HAR-derived fixture bundle, replay plan, and gate verdict
- `make demo-noui` — regenerate the sample NoUI MCP-derived fixture bundle
- `make demo-noui-redthread` — push the NoUI sample through RedThread runtime export, replay evaluation, and dry-run execution
- `make demo-redthread-runtime` — export HAR-derived fixtures into real RedThread replay inputs and evaluate them with the promotion gate
- `make demo-redthread-dryrun` — run one generated bridge case through a real RedThread dry-run campaign
- `make demo-adopt-actions` — regenerate the sample action fixture bundle
- `make demo-gate` — regenerate the replay plan and gate verdict for the catalog-style sample
- `make demo-all` — run the full local demo flow across ZAPI, NoUI, replay, and dry-run seams

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

## NoUI flow

Canonical local sequence:

```bash
python3 scripts/ingest_noui.py \
  fixtures/noui_samples/expedia_stay_search \
  fixtures/replay_packs/sample_noui_fixture_bundle.json

python3 scripts/export_redthread_runtime_inputs.py \
  fixtures/replay_packs/sample_noui_fixture_bundle.json \
  fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json

../redthread/.venv/bin/python scripts/evaluate_redthread_replay.py \
  fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json \
  fixtures/replay_packs/sample_noui_redthread_replay_verdict.json
```

What this proves:
- NoUI MCP output can be normalized into the same bridge fixture model
- the NoUI lane can reuse the same RedThread runtime export seam
- one NoUI-derived case can be evaluated by RedThread without changing RedThread core

## RedThread runtime flow

Canonical local sequence:

```bash
python3 scripts/export_redthread_runtime_inputs.py \
  fixtures/replay_packs/sample_har_fixture_bundle.json \
  fixtures/replay_packs/sample_har_redthread_runtime_inputs.json

../redthread/.venv/bin/python scripts/evaluate_redthread_replay.py \
  fixtures/replay_packs/sample_har_redthread_runtime_inputs.json \
  fixtures/replay_packs/sample_har_redthread_replay_verdict.json

../redthread/.venv/bin/python scripts/run_redthread_dryrun.py \
  fixtures/replay_packs/sample_har_redthread_runtime_inputs.json \
  fixtures/replay_packs/sample_har_redthread_dryrun_case0.json
```

What this proves:
- bridge fixtures can become a real `ReplayBundle` payload
- RedThread's real promotion gate can score that bundle
- one generated case can run through the real RedThread dry-run engine path

Later scripts:
- `classify_risk.py` — split-out classifier if the heuristics outgrow the loader

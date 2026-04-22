# Scripts

This folder will hold small MVP entrypoints.

Current scripts:
- `ingest_zapi.py` — normalize ZAPI discovery output or HAR-derived captures
- `ingest_noui.py` — normalize a NoUI MCP server output into fixtures
- `ingest_adopt_actions.py` — normalize an Adopt action catalog into fixtures
- `generate_replay_pack.py` — turn normalized fixtures into replay-pack groups
- `prepublish_gate.py` — prototype gate for approve/review/block decisions, now able to include live replay/workflow evidence and RedThread replay verdicts
- `generate_live_attack_plan.py` — create `live_attack_plan.json` with execution policy for each normalized fixture
- `run_live_safe_replay.py` — execute policy-allowed safe reads, reviewed auth-safe-read GETs, and reviewed non-destructive staging writes when explicit approved context is supplied
- `run_live_workflow_replay.py` — execute grouped sequential workflow replay from workflow and attack plans using the same auth/write guardrails
  - carries bounded state/evidence forward between steps
  - emits structured workflow failure reasons and reason counts
  - emits workflow requirement summaries, failure-class summaries, and binding review artifacts for operator/gate follow-through
- `export_redthread_runtime_inputs.py` — convert normalized fixture bundles into real RedThread replay and dry-run campaign input shapes
- `evaluate_redthread_replay.py` — evaluate exported replay traces with RedThread's actual promotion-gate code
- `run_redthread_dryrun.py` — run one exported case through a real RedThread dry-run campaign path
- `run_bridge_pipeline.py` — run the full bridge flow from one artifact input
- `run_live_zapi_bridge.py` — run live ZAPI capture, then feed the selected HAR into the full bridge flow
  - supports `--interactive` for human-guided capture
  - writes `zapi_capture/capture_metadata.json`

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
- `make demo-live-plan` — generate the sample machine-readable live attack plan
- `make demo-bridge-pipeline` — run the full one-command pipeline from the sanitized HAR sample
- `make live-zapi-bridge URL=https://example.com` — run a real ZAPI capture, then execute the full bridge flow
- `make demo-all` — run the full local demo flow across ZAPI, NoUI, replay, dry-run, and the one-command pipeline

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

## One-command bridge flow

For a sanitized HAR or other supported input artifact:

```bash
python3 scripts/run_bridge_pipeline.py \
  fixtures/zapi_samples/sample_filtered_har.json \
  runs/sample_har_pipeline \
  --ingestion zapi
```

If you want the first live safe-read lane too:

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/safe_read_capture.har \
  runs/live_safe_read_pipeline \
  --ingestion zapi \
  --run-live-safe-replay
```

If the safe read needs reviewed auth context too:

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/auth_safe_read_capture.har \
  runs/auth_safe_read_pipeline \
  --ingestion zapi \
  --run-live-safe-replay \
  --allow-reviewed-auth \
  --auth-context /path/to/approved_auth_context.json
```

If a reviewed non-destructive write should run in staging:

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/write_review_capture.har \
  runs/reviewed_write_pipeline \
  --ingestion zapi \
  --run-live-safe-replay \
  --allow-reviewed-writes \
  --write-context /path/to/approved_write_context.json
```

If grouped multi-step cases should replay in sequence too:

```bash
python3 scripts/run_bridge_pipeline.py \
  /path/to/workflow_capture.har \
  runs/live_workflow_pipeline \
  --ingestion zapi \
  --run-live-workflow-replay
```

For a live ZAPI session:

```bash
python3 scripts/run_live_zapi_bridge.py \
  "https://example.com" \
  runs/live_zapi_run \
  --zapi-repo /tmp/pi-github-repos/adoptai/zapi \
  --interactive \
  --operator-notes "log in, click billing, open profile"
```

What this proves:
- artifact capture/export can now be chained directly into bridge normalization
- a machine-readable live attack plan now exists alongside replay and gate artifacts
- the gate can now include live replay/workflow evidence and the RedThread replay verdict
- a machine-readable live workflow plan now exists for grouped multi-step cases
- grouped workflow replay now carries bounded step-to-step evidence in output artifacts
- the first live safe-read execution lane can run against allowed GET cases
- reviewed auth-bound safe-read GETs can run only with explicit approved auth context
- reviewed non-destructive writes can run only in staging with explicit per-case approved write context
- grouped multi-step workflows can replay in sequence with stop-on-first-failure behavior
- grouped workflow output now includes `final_state`, per-step `workflow_evidence`, and summary `reason_counts`
- replay/gate/runtime export no longer need separate manual commands
- RedThread replay + dry-run checks can be triggered from one top-level runner

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

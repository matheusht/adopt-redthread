# Examples

## Demo walkthroughs

- `zapi_to_replay_demo.md` — best first recruiter demo: catalog-style ZAPI discovery in, fixture bundle out, replay plan out
- `har_to_replay_demo.md` — real-input demo: HAR-derived capture in, filtered fixture bundle out, replay plan and gate out
- `redthread_runtime_demo.md` — bridge-to-engine demo: normalized fixtures into real RedThread replay and dry-run inputs
- `noui_to_redthread_demo.md` — NoUI MCP output into normalized fixtures, then into RedThread replay and dry-run seams
- `live_zapi_bridge_demo.md` — live ZAPI capture into one-command bridge outputs and RedThread checks
- `live_safe_replay_demo.md` — first policy-gated live safe-read GET replay lane

## First MVP flow

```bash
python3 scripts/ingest_zapi.py \
  fixtures/zapi_samples/sample_discovery.json \
  fixtures/replay_packs/sample_fixture_bundle.json

python3 scripts/generate_replay_pack.py \
  fixtures/replay_packs/sample_fixture_bundle.json \
  fixtures/replay_packs/sample_replay_plan.json
```

This takes a ZAPI-style discovery export and produces:
- a normalized RedThread-friendly fixture bundle
- a grouped replay plan for security validation

## HAR MVP flow

```bash
python3 scripts/ingest_zapi.py \
  fixtures/zapi_samples/sample_filtered_har.json \
  fixtures/replay_packs/sample_har_fixture_bundle.json

python3 scripts/generate_replay_pack.py \
  fixtures/replay_packs/sample_har_fixture_bundle.json \
  fixtures/replay_packs/sample_har_replay_plan.json
```

This takes a sanitized HAR-shaped capture and produces:
- a filtered, deduped fixture bundle
- a replay plan that keeps the same downstream contract as the catalog-style lane

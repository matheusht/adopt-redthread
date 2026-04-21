# NoUI to RedThread Demo

This demo shows the new NoUI bridge lane.

It starts from a real NoUI MCP output shape:
- `manifest.json`
- `tools.json`

Then it pushes that through the same bridge contract used by the ZAPI lane.

---

## What this demo proves

This demo proves:

1. NoUI MCP server output can be normalized into the common bridge fixture model
2. the NoUI lane can reuse the same RedThread runtime export path
3. RedThread can evaluate and dry-run a NoUI-derived case without any RedThread core changes

This is good because it preserves the product boundary:
- NoUI discovers and packages app operations
- Adopt RedThread adapts them
- RedThread stays the engine

---

## Canonical flow

Normalize the NoUI MCP server output:

```bash
python3 scripts/ingest_noui.py \
  fixtures/noui_samples/expedia_stay_search \
  fixtures/replay_packs/sample_noui_fixture_bundle.json
```

Export into RedThread runtime inputs:

```bash
python3 scripts/export_redthread_runtime_inputs.py \
  fixtures/replay_packs/sample_noui_fixture_bundle.json \
  fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json
```

Evaluate with RedThread's replay gate:

```bash
../redthread/.venv/bin/python scripts/evaluate_redthread_replay.py \
  fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json \
  fixtures/replay_packs/sample_noui_redthread_replay_verdict.json
```

Run one dry-run case through RedThread:

```bash
../redthread/.venv/bin/python scripts/run_redthread_dryrun.py \
  fixtures/replay_packs/sample_noui_redthread_runtime_inputs.json \
  fixtures/replay_packs/sample_noui_redthread_dryrun_case0.json
```

Or use shortcuts:

```bash
make demo-noui
make demo-noui-redthread
```

---

## What the sample means

The sample NoUI server comes from a public Expedia-style MCP example.
The bridge extracts one tool:
- `search_hotels`

The resulting normalized fixture keeps useful security hints such as:
- auth required
- browser-session execution strategy
- MCP/runtime context
- query parameter surface
- response field surface

That is stronger than plain endpoint discovery alone.

---

## Why this matters

This step makes the bridge more realistic for agent-builder ecosystems.

It means we now support:
- ZAPI-style endpoint discovery
- HAR-derived endpoint discovery
- NoUI MCP tool discovery
- RedThread replay export
- RedThread dry-run execution export

That is the first believable shape of a multi-input adapter layer.

---

## Still keep scope honest

This does **not** mean:
- full live NoUI runtime interception
- Tabby session control inside RedThread
- production publish gates

It means the bridge can consume one real NoUI artifact family and hand it off into real RedThread seams.

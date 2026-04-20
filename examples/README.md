# Examples

## Demo walkthroughs

- `zapi_to_replay_demo.md` — best first recruiter demo: ZAPI-style discovery in, fixture bundle out, replay plan out

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

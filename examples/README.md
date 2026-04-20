# Examples

## First MVP flow

```bash
python3 scripts/ingest_zapi.py \
  fixtures/zapi_samples/sample_discovery.json \
  fixtures/replay_packs/sample_fixture_bundle.json
```

This takes a ZAPI-style discovery export and produces a normalized RedThread-friendly fixture bundle.

Use this as the first recruiter demo seam:
- discovery intake
- endpoint risk classification
- replay planning metadata

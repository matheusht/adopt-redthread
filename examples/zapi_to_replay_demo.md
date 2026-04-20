# ZAPI to Replay Demo

This is the first clean recruiter demo for **Adopt RedThread**.

It shows a simple but powerful seam:

1. discover app capabilities with a ZAPI-style export
2. normalize them into RedThread-friendly fixtures
3. generate a replay pack grouped by risk and execution mode

---

## Why this demo matters

This demo proves the repo is not just ideas.

It already connects:
- discovery intake
- risk classification
- replay planning

That is the first practical step toward a real pre-publish security gate.

---

## Files used

### Input
- `fixtures/zapi_samples/sample_discovery.json`

### Intermediate output
- `fixtures/replay_packs/sample_fixture_bundle.json`

### Final replay-pack output
- `fixtures/replay_packs/sample_replay_plan.json`

---

## Step 1 — Normalize ZAPI discovery output

Run:

```bash
python3 scripts/ingest_zapi.py \
  fixtures/zapi_samples/sample_discovery.json \
  fixtures/replay_packs/sample_fixture_bundle.json
```

What this does:
- reads discovered endpoints
- tags risk level
- tags replay class
- infers approval and sensitivity hints
- suggests candidate attack types

Example classification ideas:
- authenticated read paths become `safe_read_with_review`
- write paths become `manual_review`
- destructive admin paths become `sandbox_only`

---

## Step 2 — Generate replay pack

Run:

```bash
python3 scripts/generate_replay_pack.py \
  fixtures/replay_packs/sample_fixture_bundle.json \
  fixtures/replay_packs/sample_replay_plan.json
```

What this does:
- groups safe read probes
- groups write-path review items
- groups sandbox-only attack items

This turns discovery output into something the security layer can act on.

---

## What the replay pack means

### Safe read probes
Use for:
- least-privilege checks
- overbroad retrieval checks
- data leakage checks

### Write-path review items
Use for:
- unsafe write activation testing
- approval-boundary checks
- parameter-grounding checks

### Sandbox-only attack set
Use for:
- destructive or privileged actions
- deny-before-send controls
- audit-log validation in staging

---

## Recruiter-friendly story

Short version:

> I kept RedThread standalone as the core security system, then built a separate bridge repo that can ingest Adopt-style discovery artifacts and turn them into replayable security plans.

This shows:
- system design
- practical agent security thinking
- product-minded risk reduction
- the start of a release-gate architecture

---

## Best live walkthrough

When demoing this repo:

1. show the sample discovery JSON
2. run `ingest_zapi.py`
3. open the normalized fixture bundle
4. run `generate_replay_pack.py`
5. open the replay plan
6. explain how this would later feed RedThread attack and validation flows

Keep it short and crisp.
The point is to show the seam clearly.

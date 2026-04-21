# HAR to Replay Demo

This demo shows the new real-input bridge lane.

It keeps the project boundary honest:
- Adopt discovery gives the raw surface
- Adopt RedThread adapts that surface into fixtures
- RedThread stays the engine that will later attack, replay, validate, and harden

---

## What this demo proves

This demo proves that a HAR-shaped discovery artifact can be turned into:
- normalized RedThread-friendly fixtures
- a replay plan
- a gate verdict

It does **not** prove:
- live RedThread execution against the target
- full support for every ZAPI output shape
- safe production replay of live write operations

---

## Safe sample flow

Use the sanitized sample HAR in this repo:

```bash
python3 scripts/ingest_zapi.py \
  fixtures/zapi_samples/sample_filtered_har.json \
  fixtures/replay_packs/sample_har_fixture_bundle.json

python3 scripts/generate_replay_pack.py \
  fixtures/replay_packs/sample_har_fixture_bundle.json \
  fixtures/replay_packs/sample_har_replay_plan.json

python3 scripts/prepublish_gate.py \
  fixtures/replay_packs/sample_har_replay_plan.json \
  fixtures/replay_packs/sample_har_gate_verdict.json
```

Or use the shortcut:

```bash
make demo-zapi-har
```

---

## What the adapter does

The HAR adapter is conservative on purpose.

It tries to:
- keep app-like API calls
- drop static assets like JS, CSS, and images
- drop common analytics and third-party transport noise
- drop obvious telemetry-only endpoints like `event/report`
- dedupe repeated calls by `method + path`

That means the output is smaller and more useful than the raw HAR.

---

## Expected sample result

For the sanitized sample, the bridge keeps these four fixtures:

- `post_weaver_api_v1_conversation_accept_msg`
- `post_weaver_api_v1_ugc_memory_get_memory_detail`
- `post_weaver_api_v1_payment_subscription_list_v2`
- `post_weaver_api_v1_user_set_user_preference`

And it drops low-value noise such as:
- Google Analytics traffic
- `event/report`

---

## How to use a real local HAR

Keep the raw HAR local.
Do not commit it.

Then run:

```bash
python3 scripts/ingest_zapi.py /path/to/demo_session_filtered.har /path/to/output_fixture_bundle.json
python3 scripts/generate_replay_pack.py /path/to/output_fixture_bundle.json /path/to/output_replay_plan.json
python3 scripts/prepublish_gate.py /path/to/output_replay_plan.json /path/to/output_gate_verdict.json
```

After that:
- inspect the normalized fixture bundle
- verify sensitive values are not carried into committed artifacts
- use the reduced bundle as the durable bridge artifact

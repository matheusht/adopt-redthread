# ATP Tennis ZAPI Reference Demo

## What this demo is

This is the current real ZAPI reference proof for Adopt RedThread:

```text
runs/atp_tennis_01_live_bound/
```

It was produced from the ignored raw HAR:

```text
demo_session_filtered.har
```

The raw HAR and full run directory are intentionally not checked in. They can contain session-derived headers, cookies, IDs, request bodies, or app data. The checked-in durable artifact is the sanitized expected summary:

```text
fixtures/reference_demos/atp_tennis_zapi_reference_expected.json
```

## One-command check

With the local HAR and local run artifacts present, run:

```bash
make check-zapi-reference
```

This validates the raw HAR extraction and the saved run evidence, then writes a non-secret summary to:

```text
runs/atp_tennis_reference_check/sanitized_evidence.json
```

The check does **not** re-run the live workflow by default. That is deliberate: live endpoint behavior can drift, credentials can expire, and replaying reviewed writes should remain explicit. This command verifies the saved proof without copying sensitive data into git.

## Expected result

The correct result is **review**, not approve.

Expected evidence:

- input file basename: `demo_session_filtered.har`
- ingestion: `zapi`
- fixture count from HAR: `5`
- live workflow count: `1`
- live workflow replay executed: `true`
- successful workflow count: `1`
- blocked workflow count: `0`
- aborted workflow count: `0`
- declared response bindings: `3`
- applied response bindings: `3`
- RedThread replay passed: `true`
- RedThread dry-run executed: `true`
- local gate decision: `review`
- gate warning: `manual_review_required_for_write_paths`
- workflow class: `reviewed_write_workflow`

## Why `review` is the right outcome

This reference includes write paths. Even when the workflow succeeds, bindings apply, and RedThread replay passes, the gate should not silently auto-approve write-path behavior.

The point of this demo is therefore:

```text
real ZAPI/HAR artifact
  -> normalized fixtures
  -> reviewed write workflow plan
  -> live workflow replay evidence
  -> RedThread runtime/replay evidence
  -> local gate result: review
```

That proves the bridge preserves risk semantics instead of forcing a happy-path approve.

## What this proves

Proven:

- the HAR produces the expected normalized ZAPI fixture shape
- the real reference run contains successful bridge-owned workflow replay evidence
- response bindings were declared and applied
- RedThread replay accepted the generated runtime evidence
- the local gate correctly downgraded the result to `review` because write paths require manual review

Not proven:

- fully autonomous production Adopt -> RedThread publish gating
- stable live replay against this endpoint forever
- broad authenticated write coverage beyond this reviewed path
- RedThread independently owning live workflow execution for Adopt-managed sessions

## If live replay is attempted again

A fresh live replay may differ from the saved proof because the ATP app is external and can stream, timeout, mutate responses, or change session behavior. If that happens, do not rewrite the demo as approve. Record the new result honestly and keep `review`/`block` semantics intact.

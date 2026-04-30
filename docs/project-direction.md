# Project Direction, Scope, and Proof Standard

## Direction

Adopt RedThread is the integration bridge between Adopt-style tool discovery/building and RedThread security assurance.

The product direction is intentionally narrow:

1. Adopt/ZAPI/NoUI discover or describe app operations.
2. This repo normalizes those operations into security-testable fixtures, live replay plans, workflow evidence, and RedThread runtime inputs.
3. RedThread evaluates the normalized replay/campaign inputs and returns security evidence such as replay verdicts and dry-run results.
4. This repo's local pre-publish gate combines bridge evidence plus RedThread evidence into `approve`, `review`, or `block`.

That last point is important: **today RedThread's replay verdict is an input to the final decision, not the final final decision itself.** The final `approve/review/block` verdict currently comes from this repo's local gate.

## Decision posture

The current decision is to keep `runs/` as generated local evidence, not as the durable source of truth.

Reason:
- real runs can contain HAR-derived session state, cookies, IDs, headers, request bodies, or app data
- tracking all `runs/` would make drift less likely but would make accidental sensitive-artifact commits more likely
- a tiny deterministic generator plus tests gives durability without committing raw run output

So the durable paths are:

```bash
make demo-hero-binding-truth
make demo-reviewed-write-reference
python3 -m unittest tests.test_golden_demo_truth tests.test_reviewed_write_reference -v
```

Generated artifacts still live in:

```text
runs/hero_binding_truth/
```

But they are reproducible, not the canonical checked-in artifact.

## Current scope

In scope now:

- ZAPI catalog and HAR-shaped artifact ingestion
- NoUI MCP manifest/tools ingestion for the first supported shape
- Adopt action catalog ingestion
- normalized fixture generation
- live attack planning
- bounded live safe-read and reviewed workflow replay owned by this repo
- workflow state/evidence carry-forward
- runtime response-binding evidence: planned, applied, unapplied, failed
- RedThread replay-bundle export
- RedThread replay evaluation with real RedThread code
- RedThread dry-run campaign execution for generated cases
- local pre-publish gate experiments
- demo-quality proof artifacts and docs

Out of scope for now:

- direct pull from real Adopt services
- fully automatic production Adopt -> RedThread live attack orchestration
- broad NoUI format coverage beyond the first MCP shape
- production publish gating
- general-purpose scanner integrations
- outreach automation or unrelated platform expansion

## Desired result

The desired near-term result is one credible proof path that a reviewer can inspect without believing marketing claims:

```text
Discovery artifact
  -> normalized fixtures
  -> live/workflow replay evidence
  -> RedThread runtime input
  -> RedThread replay/dry-run evidence
  -> local gate decision: approve / review / block
```

The strongest demo outcome is not always `approve`. A real workflow with reviewed writes should usually land in `review`, because human approval is still required for write-path safety.

## Impact standard

A demo only counts when it shows evidence, not just architecture.

Minimum credible evidence:

- the input artifact is visible or reproducible
- generated fixture count is visible
- replay/workflow execution status is visible
- binding/runtime context is visible when workflows depend on prior responses
- RedThread replay verdict is visible
- the local gate decision is visible
- `review` and `block` are treated as valid security outcomes, not failures to be hidden

## Deterministic reviewed-write reference demo

The deterministic reviewed-write reference is:

```bash
make demo-reviewed-write-reference
```

It writes:

```text
runs/reviewed_write_reference/evidence_report.md
```

This is the operator-friendly local proof path. It hides the generated HAR, auth context, write context, response-binding overrides, RedThread runtime input, and gate files behind one command while still leaving those artifacts inspectable under `runs/reviewed_write_reference/`.

Expected result:

- fixture count: `5`
- reviewed workflow count: `1`
- declared response bindings: `3`
- applied response bindings: `3`
- RedThread replay passed: yes
- final gate decision: `review`
- reason: `manual_review_required_for_write_paths`

## Real ZAPI reference demo

The current real ZAPI reference is:

```text
runs/atp_tennis_01_live_bound/
```

Validate it with:

```bash
make check-zapi-reference
```

It should be described as a **review** demo, not an approve demo.

Why:

- input: `demo_session_filtered.har`
- ingestion: `zapi`
- live workflow replay executed: yes
- workflow succeeded: yes
- declared response bindings: `3`
- applied response bindings: `3`
- RedThread replay passed: yes
- final gate decision: `review`
- reason: `manual_review_required_for_write_paths`

The raw HAR and full run artifacts stay ignored. The checked-in canonical reference is the sanitized expectation file:

```text
fixtures/reference_demos/atp_tennis_zapi_reference_expected.json
```

This is the right outcome for a real-ish workflow that includes reviewed write paths. It proves the bridge can carry live workflow evidence and RedThread evidence into a conservative gate, not that every workflow should auto-approve.

## What is proven vs not proven yet

### Proven

- Artifact translation: ZAPI/HAR, NoUI MCP, and Adopt action samples can become normalized bridge fixtures.
- Live workflow evidence: this repo can execute bounded grouped workflows and record planned/applied/failed runtime binding facts.
- RedThread handoff: normalized fixtures can become RedThread replay bundles and dry-run campaign cases, and real RedThread code can evaluate them.
- Gate integration: this repo can combine live replay evidence plus RedThread replay verdicts into `approve`, `review`, or `block`.

### Not proven yet

- A full production Adopt -> RedThread autonomous risk-validation loop.
- RedThread independently driving live attacks against an Adopt-managed runtime immediately after discovery.
- Production-grade publish gating wired into an actual release system.
- Broad authenticated/session-aware replay beyond explicit approved context slices.
- Broad reviewed write coverage beyond the first non-destructive staging path.

## Operating rule

Do fewer things, with harder proof.

Do not add new platform scope until the canonical proof path is boringly reproducible and the real ZAPI reference demo is documented honestly as `review`.

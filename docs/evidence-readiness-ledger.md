# Evidence Readiness Ledger

## Purpose

The evidence readiness ledger gives one local, sanitized view of whether the current reviewer evidence package is ready to discuss, still waiting on external validation, blocked by privacy/freshness problems, or blocked by missing artifacts.

It is deliberately conservative. It indexes generated evidence metadata; it does not approve a release.

## Command

```bash
make evidence-readiness
```

Default output:

```text
runs/evidence_readiness/
├── evidence_readiness.md
└── evidence_readiness.json
```

Schema:

```text
adopt_redthread.evidence_readiness.v1
```

The command regenerates `runs/evidence_freshness/evidence_freshness_manifest.{md,json}`, `runs/external_review_returns/external_review_return_ledger.{md,json}`, and the sanitized boundary context request package first, then builds the readiness ledger from sanitized metadata.

## Inputs

The ledger reads these generated JSON artifacts:

- `runs/evidence_matrix/evidence_matrix.json`
- `runs/reviewer_packet/reviewer_packet.json`
- `runs/external_review_handoff/external_review_handoff_manifest.json`
- `runs/external_review_sessions/external_review_session_batch.json`
- `runs/external_validation_readout/external_validation_readout.json`
- `runs/external_review_returns/external_review_return_ledger.json`
- `runs/boundary_probe_context/tenant_user_boundary_probe_context.template.json`
- `runs/boundary_probe_context_request/tenant_user_boundary_probe_context_request.json`
- `runs/boundary_probe_result/tenant_user_boundary_probe_result.json`
- `runs/evidence_freshness/evidence_freshness_manifest.json`

It also runs the configured sensitive-marker audit over those known inputs. That audit is a bounded privacy tripwire, not a complete secret scanner.

## What it never includes

The readiness ledger must not include:

- raw HAR/session/cookie/auth/header/body/request/response data
- source files
- raw reviewer free-form answers
- production or staging write-context values
- raw boundary actor, tenant, resource, selector, credential, request-body, or response-body values

## Statuses

- `privacy_blocked` — at least one configured sensitive-marker audit failed.
- `missing_required_evidence` — a required generated JSON artifact is missing or has the wrong schema.
- `stale_or_missing_evidence` — freshness checks found stale/missing copied reviewer artifacts.
- `waiting_for_external_validation` — sanitized evidence is present, but external reviewer summaries are not yet ready.
- `boundary_context_pending` — external validation is otherwise ready, but boundary context is not ready or boundary probe execution still has not happened.
- `needs_decision_example_coverage` — the matrix does not contain approve/review/block examples.
- `ready_for_sanitized_readout` — required sanitized artifacts are present, fresh, marker-clean, and external validation readout is ready.

Current expected local state before real external reviews is usually:

```text
waiting_for_external_validation
```

That is a correct non-claim, not a failure.

## Blocker semantics

The ledger records blocker labels such as:

- `external_validation_not_ready`
- `external_review_returns_not_ready`
- `boundary_context_not_ready`
- `boundary_context_request_not_ready`
- `boundary_probe_not_executed`
- `stale_or_missing_evidence_copies`
- `privacy_marker_audit_failed`
- `missing_required_evidence`

These labels are readiness blockers for reviewer evidence packaging. They do not replace the bridge gate decision and do not change `approve` / `review` / `block` verdict semantics.

## Recommended next actions

The ledger emits next actions from the blockers. Examples:

- collect and summarize external reviewer observations, with per-review return status visible in the return ledger
- regenerate stale handoff/session copies
- regenerate the sanitized boundary context request package when the request artifact is missing, invalid, or privacy-blocked
- generate the sanitized boundary context request package when approved context metadata is missing
- validate sanitized boundary context metadata before any future boundary execution
- keep boundary execution blocked until approved non-production tenant/user context exists
- keep `boundary_probe_not_executed` open even when context is `ready_for_boundary_probe`, because ready context is not execution proof
- remove/regenerate artifacts that hit configured sensitive-marker checks

Readiness indexes the return ledger status and bounded boundary-context-request delivery coverage. For per-review external return status after distribution, run:

```bash
make evidence-external-review-returns
```

For boundary context intake status without executing probes, run:

```bash
make evidence-boundary-probe-context
```

For the sanitized missing-context request/checklist, run:

```bash
make evidence-boundary-context-request
```

For an ordered work queue with owner labels, priorities, verification commands, and acceptance criteria, run:

```bash
make evidence-remediation-queue
```

## Non-claims

The readiness ledger does not prove:

- production publish approval
- buyer demand
- production readiness
- whole-app safety
- external validation before filled observations are summarized
- approved boundary context
- boundary execution proof

It is an index for the current sanitized evidence loop, not a new gate owner.

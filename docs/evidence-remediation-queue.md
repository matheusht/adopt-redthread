# Evidence Remediation Queue

## Purpose

The evidence remediation queue converts sanitized readiness and distribution blockers into an ordered local work queue.

It exists so the next action is explicit instead of hidden across several generated artifacts. It is not a release gate and not validation evidence.

## Command

```bash
make evidence-remediation-queue

# Optional: carry approved-context replay state through regenerated readiness.
make evidence-remediation-queue \
  EVIDENCE_APPROVED_REPLAY_RESULT=runs/approved_context_replay/approved_context_replay_result.json
```

Default output:

```text
runs/evidence_remediation/
├── evidence_remediation_queue.md
└── evidence_remediation_queue.json
```

Schema:

```text
adopt_redthread.evidence_remediation_queue.v1
```

By default the command regenerates `runs/evidence_readiness/evidence_readiness.{md,json}` first. Readiness regeneration also refreshes the external review return ledger, freshness manifest, and boundary context request package. The queue then reads the current external review distribution manifest if present.

## Inputs

The queue reads sanitized generated metadata only:

- `runs/evidence_readiness/evidence_readiness.json`
- `runs/external_review_distribution/external_review_distribution_manifest.json`

The queue command list also points operators through `make evidence-external-review-returns` after per-review summaries are generated, so missing/incomplete/follow-up state is visible before the external validation readout is interpreted.

The readiness ledger already indexes matrix, packet, handoff, sessions, validation readout, external review returns, boundary context, boundary context request, boundary result, freshness, and optional approved-context replay state when supplied. The queue does not reopen raw app artifacts.

## What it never includes

The queue must not include:

- raw HAR/session material
- credentials or auth material
- request or response bodies
- source files
- staging or production write-context values
- raw boundary actor, tenant, resource, selector, credential, request, or response values
- reviewer free-form answers

## Statuses

- `privacy_blocked` — configured sensitive-marker audit failed in the queue inputs or embedded source audits.
- `open_items` — sanitized blockers exist and have been converted into work items.
- `no_open_items` — no readiness or distribution blockers remain.

Current expected local status before real external reviews is:

```text
open_items
```

The current queue should normally contain some combination of:

1. `collect_external_reviewer_observations`
2. `validate_approved_boundary_context` or `wait_for_boundary_probe_execution`
3. `complete_approved_context_replay_execution` when an optional approved-context replay result is indexed but not executed

If the request artifact itself is missing, invalid, or privacy-blocked, the queue may first add `regenerate_boundary_context_request`. If the return ledger is waiting/incomplete, the queue keeps the existing `collect_external_reviewer_observations` item and includes return-ledger verification.

That is the correct honest state: external validation is still waiting on humans, boundary execution is still blocked until separately approved/executed, and endpoint replay planning/approval requests are not execution proof.

For `complete_approved_context_replay_execution`, the queue now reads sanitized approval-scope facts from readiness. It can distinguish:

- no approval supplied: `blocked_on_operator_execution_approval`
- approval supplied with missing explicit scope: `blocked_on_scoped_execution_approval`
- approval supplied for the wrong case/mode: `blocked_on_matching_execution_approval`
- approval supplied with wildcard scope: `blocked_on_narrow_execution_approval`
- approval supplied and scoped, but not executed: `blocked_on_execute_flag`

All of these remain blocked states until approved non-production context, explicit scoped approval, and the execute flag are present together.

## Work item fields

Each item records:

- `id`
- priority
- owner label
- status
- source blocker
- blocked-by list
- action
- verification commands
- acceptance criteria
- non-claim

The owner labels are coordination labels, not live Paperclip assignments.

## Current command queue

In the current no-reviewer state, the generated queue points to the per-review commands from the distribution manifest:

```bash
make evidence-observation-summary OBSERVATION=runs/external_review_sessions/review_1/filled_reviewer_observation.md OBSERVATION_OUTPUT=runs/external_review_sessions/review_1
make evidence-observation-summary OBSERVATION=runs/external_review_sessions/review_2/filled_reviewer_observation.md OBSERVATION_OUTPUT=runs/external_review_sessions/review_2
make evidence-observation-summary OBSERVATION=runs/external_review_sessions/review_3/filled_reviewer_observation.md OBSERVATION_OUTPUT=runs/external_review_sessions/review_3
make evidence-external-review-returns
make evidence-external-validation-readout
make evidence-readiness
make evidence-approved-context-replay-approval-request APPROVED_REPLAY_OUTPUT=runs/approved_context_replay
make evidence-approved-context-replay APPROVED_REPLAY_CASE=case_id APPROVED_REPLAY_OUTPUT=runs/approved_context_replay APPROVED_REPLAY_EXECUTION_APPROVAL=path/to/local_approval.json APPROVED_REPLAY_EXECUTE=1
make evidence-boundary-context-request
make evidence-boundary-probe-context BOUNDARY_CONTEXT=path/to/sanitized_context.json
make evidence-boundary-probe-context
make evidence-boundary-probe-result
```

Boundary-related commands remain blocked until approved non-production tenant/user context exists and a separate boundary execution window exists. Approved-context replay execution commands remain blocked until a sanitized approval artifact exists, the approval artifact has explicit matching case/mode scope, and the operator explicitly approves the non-production execution window. Wildcard approval scope is rejected. Regenerating default/request artifacts is allowed; treating `ready_for_boundary_probe` context, approval requests, or default result templates as execution proof is not.

## Non-claims

The remediation queue does not prove:

- release approval
- external human validation
- buyer demand
- production readiness
- approved boundary context
- approved-context replay execution before it actually runs
- boundary execution
- whole-app safety

It does not change local bridge `approve` / `review` / `block` semantics.

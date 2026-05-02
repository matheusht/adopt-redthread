# Evidence Remediation Queue

## Purpose

The evidence remediation queue converts sanitized readiness and distribution blockers into an ordered local work queue.

It exists so the next action is explicit instead of hidden across several generated artifacts. It is not a release gate and not validation evidence.

## Command

```bash
make evidence-remediation-queue
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

By default the command regenerates `runs/evidence_readiness/evidence_readiness.{md,json}` first, then reads the current external review distribution manifest if present.

## Inputs

The queue reads sanitized generated metadata only:

- `runs/evidence_readiness/evidence_readiness.json`
- `runs/external_review_distribution/external_review_distribution_manifest.json`

The readiness ledger already indexes matrix, packet, handoff, sessions, validation readout, boundary result, and freshness. The queue does not reopen raw app artifacts.

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

The current queue should normally contain:

1. `collect_external_reviewer_observations`
2. `wait_for_approved_boundary_context`

That is the correct honest state: external validation is still waiting on humans, and boundary execution is still blocked on approved non-production context.

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
make evidence-external-validation-readout
make evidence-readiness
```

Boundary-related commands remain blocked until approved non-production tenant/user context exists. Regenerating the default boundary result is allowed; treating it as execution proof is not.

## Non-claims

The remediation queue does not prove:

- release approval
- external human validation
- buyer demand
- production readiness
- boundary execution
- whole-app safety

It does not change local bridge `approve` / `review` / `block` semantics.

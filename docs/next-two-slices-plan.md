# Next Two Slices Plan

Date: 2026-05-01

## Scope

Implement only local, privacy-preserving evidence-loop mechanics. Do not build a live boundary executor, do not run production or staging probes, do not add a new integration, and do not change `approve` / `review` / `block` semantics.

These slices follow the completed evidence freshness manifest and evidence readiness ledger work.

## Slice 1 — External review distribution manifest

### Objective

Turn the generated external review session batch into a precise send list for operators. The manifest should say which isolated `review_N` folders may be distributed, whether the copies are fresh, and which sanitized observation summary path is expected back from each reviewer.

### Implemented artifacts

- `scripts/build_external_review_distribution_manifest.py`
- `make evidence-external-review-distribution`
- `runs/external_review_distribution/external_review_distribution_manifest.{md,json}` generated locally
- `tests/test_external_review_distribution.py`
- `docs/external-review-distribution-manifest.md`

### Acceptance criteria

- Reads only the sanitized external handoff manifest, external session batch, freshness manifest, copied sanitized session artifacts, and blank observation templates.
- Reports `ready_to_distribute`, `privacy_blocked`, `missing_required_evidence`, `stale_or_missing_evidence`, or `not_ready_to_distribute`.
- Blocks distribution when freshness is stale/missing or required schemas are absent/invalid.
- Emits one delivery entry per reviewer session with allowed file count, filled observation path, expected summary path, and exact summary command.
- Fails closed on configured sensitive-marker hits.
- States clearly that distribution is not external validation, not buyer-demand proof, not production-readiness proof, not boundary execution proof, and not a verdict-semantics change.
- Does not read or copy raw HAR/session/cookie/auth/header/body/request/response data, source files, write-context values, raw boundary values, or prior reviewer answers.

### Current local result

- `distribution_status: ready_to_distribute`
- `delivery_count: 3`
- `blocker_count: 0`

This means the isolated session folders are ready to send. It does not mean the reviewers have validated anything yet.

## Slice 2 — Evidence remediation queue

### Objective

Convert the sanitized readiness/distribution state into an ordered action queue. The queue should make the next work explicit without changing gate semantics or pretending blocked external/boundary work is complete.

### Implemented artifacts

- `scripts/build_evidence_remediation_queue.py`
- `make evidence-remediation-queue`
- `runs/evidence_remediation/evidence_remediation_queue.{md,json}` generated locally
- `tests/test_evidence_remediation_queue.py`
- `docs/evidence-remediation-queue.md`

### Acceptance criteria

- Reads only sanitized readiness and distribution metadata.
- Regenerates the readiness ledger by default before building the queue.
- Converts readiness blockers into concrete items with owner label, priority, status, blocked-by list, action, verification commands, acceptance criteria, and non-claim.
- Preserves current no-reviewer state as `open_items`, not validation failure or release approval.
- Preserves boundary non-execution as blocked on approved non-production context, not a confirmed vulnerability.
- Fails closed on configured sensitive-marker hits, including embedded source audit metadata.
- Does not include raw reviewer free-form answers or raw app/run artifacts.
- Does not claim buyer demand, production readiness, whole-app safety, boundary execution, or RedThread ownership of the final bridge gate.

### Current local result

- `queue_status: open_items`
- `item_count: 2`
- open items:
  - `collect_external_reviewer_observations`
  - `wait_for_approved_boundary_context`

This is the correct local state. The evidence package can be distributed, but external validation and boundary execution remain incomplete.

## Still blocked after these slices

Actual external validation is still blocked until real external reviewers fill the session observations and those observations are summarized. Boundary execution remains blocked until approved non-production context exists with safe actor scopes, selector bindings, and operator approval. These slices make distribution and remediation state explicit; they do not execute probes, contact reviewers, or approve release.

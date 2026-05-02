# External Review Distribution Manifest

## Purpose

The external review distribution manifest is the operator-facing send list for external cold-review sessions. It answers one practical question:

> Which isolated session folders are fresh enough to send, and what sanitized summary path should come back from each reviewer?

It is packaging control-plane evidence only. It does not contact reviewers, does not summarize reviewer answers, and does not create validation evidence.

## Command

```bash
make evidence-external-review-distribution
```

Default output:

```text
runs/external_review_distribution/
├── external_review_distribution_manifest.md
└── external_review_distribution_manifest.json
```

Schema:

```text
adopt_redthread.external_review_distribution_manifest.v1
```

## Inputs

The manifest reads only generated sanitized metadata and the already-created session artifacts:

- `runs/external_review_handoff/external_review_handoff_manifest.json`
- `runs/external_review_sessions/external_review_session_batch.json`
- `runs/evidence_freshness/evidence_freshness_manifest.json`
- sanitized markdown files already copied under `runs/external_review_sessions/review_*/artifacts/`
- blank `filled_reviewer_observation.md` templates under each review folder

It runs the configured sensitive-marker audit over those known inputs. The audit is a privacy tripwire, not a complete secret scanner.

## What it never reads or packages

The distribution manifest must not read or include:

- raw HAR/session material
- credentials or auth material
- request or response bodies
- source files
- staging or production write-context values
- raw boundary actor, tenant, resource, selector, credential, request, or response values
- approved context files or filled local context values
- prior reviewer answers

## Statuses

- `ready_to_distribute` — handoff, session batch, and freshness metadata are valid; freshness is `fresh`; marker audit passed; delivery count satisfies the target review count.
- `privacy_blocked` — configured sensitive-marker audit failed.
- `missing_required_evidence` — a required manifest is missing or has the wrong schema.
- `stale_or_missing_evidence` — freshness metadata reports stale or missing copied artifacts.
- `not_ready_to_distribute` — generated metadata exists but the handoff/session state is not ready.

Current expected local status after regenerating handoff, sessions, and freshness is:

```text
ready_to_distribute
```

That means the session folders may be sent to reviewers. It does not mean any reviewer has validated the evidence.

## Delivery records

Each delivery entry records:

- `session_id`
- `session_dir`
- `artifact_dir`
- allowed sanitized files and hashes
- `filled_observation_path`
- `expected_summary_path`
- exact `make evidence-observation-summary ...` command for that reviewer

The operator rule is strict: send exactly one `review_N` folder to exactly one reviewer. Do not mix folders, do not include repo access, and do not include prior reviewer answers. If the folder includes `tenant_user_boundary_probe_context_request.md`, treat it as a sanitized checklist/request only; do not attach approved context or raw tenant/user values.

After reviewers return filled observations and their sanitized summaries are generated, run:

```bash
make evidence-external-review-returns
```

That return ledger reports which expected summaries are still missing, incomplete, privacy-blocked, decision-follow-up-needed, or complete.

## Non-claims

The distribution manifest does not prove:

- external human validation
- buyer demand
- production readiness
- boundary execution
- whole-app safety

It does not change local bridge `approve` / `review` / `block` semantics.

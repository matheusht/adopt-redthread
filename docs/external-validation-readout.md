# External Validation Readout

## Purpose

The external validation readout summarizes whether the external review session batch has enough complete sanitized reviewer summaries to discuss validation results.

It does not read raw observations. It consumes only:

- `runs/external_review_sessions/external_review_session_batch.json`
- `reviewer_observation_summary.json` files produced by `make evidence-observation-summary`

## Build sequence

Create the handoff and reviewer sessions first:

```bash
make evidence-external-review-handoff
make evidence-external-review-sessions
```

Before distribution, build the freshness/readiness/distribution surfaces. After reviewers fill observations and each observation is summarized, build the readout and refresh readiness/remediation:

```bash
make evidence-freshness
make evidence-readiness
make evidence-external-review-distribution
make evidence-external-review-returns
make evidence-external-validation-readout
make evidence-readiness
make evidence-remediation-queue
```

Generated local output:

```text
runs/external_validation_readout/
├── external_validation_readout.md
├── external_validation_readout.json
├── reviewer_validation_rollup.md
└── reviewer_validation_rollup.json
```

The readout writes a local rollup copy because it reuses the existing reviewer-validation rollup logic.

## Status values

`readout_status` can be:

- `waiting_for_filled_external_observations` — expected summaries are all missing; no external validation exists yet
- `needs_valid_external_observation_summaries` — some summary files are missing, invalid, or incomplete
- `needs_more_complete_external_reviews` — valid summaries exist, but fewer than the target count are complete
- `needs_external_decision_language_followup` — complete summaries exist but reviewer decision wording is inconsistent
- `ready_for_external_validation_readout` — enough complete sanitized summaries exist to discuss the result
- `privacy_blocked` — configured sensitive-marker audit failed
- `needs_valid_external_review_session_batch` — the session batch manifest is missing or invalid

## Validation claim policy

The readout deliberately separates mechanics from claims:

- Before `ready_for_external_validation_readout`, it records `not_external_validation_until_required_complete_sanitized_observation_summaries_exist`.
- At `ready_for_external_validation_readout`, it records `external_human_validation_readout_ready_but_not_buyer_demand_or_production_readiness_proof`.

Even a ready readout does not prove buyer demand, whole-product safety, production readiness, or RedThread ownership of the final bridge gate.

## Privacy boundary

The readout does not copy raw reviewer answer text. It includes only bounded counts and sanitized rollup fields:

- complete/incomplete summary counts
- normalized decision counts
- behavior-change count
- next-probe request count
- repeat-review request count
- bounded theme counts
- configured sensitive-marker audit result
- recommended next actions

Forbidden inputs remain forbidden:

- raw HAR files
- session cookies or auth headers
- request bodies or response bodies
- production or staging write-context values
- source files or repo context
- prior reviewer answers before silent review

## Relationship to freshness, readiness, distribution, returns, and remediation

After the readout is built, `make evidence-freshness` checks that copied reviewer-facing artifacts still match their sanitized source hashes. `make evidence-readiness` then indexes the matrix, packet, handoff, sessions, validation readout, boundary context, boundary result, and freshness manifest into one sanitized readiness state. `make evidence-external-review-distribution` records the exact reviewer folders and expected summary paths. `make evidence-external-review-returns` reports per-review return status without reading filled observation markdown or copying free-form reviewer answers. `make evidence-remediation-queue` converts the remaining readiness/distribution blockers into concrete next actions. With no filled external observations, the readiness ledger should remain `waiting_for_external_validation`, the return ledger should remain `waiting_for_returns`, and the remediation queue should keep `collect_external_reviewer_observations` open.

## Relationship to existing rollup

`make evidence-validation-rollup` remains the generic rollup command for any sanitized reviewer-observation summaries.

`make evidence-external-validation-readout` is narrower. It reads the external review session batch manifest, uses the expected per-session summary paths, then presents the result with external-validation wording and non-claims.

## Safety boundary

This command does not execute live probes, does not authorize write context, does not alter `approve` / `review` / `block` semantics, and does not remove `tenant_user_boundary_unproven` from evidence. It only reports whether the external reviewer evidence loop has enough complete sanitized summaries to discuss.

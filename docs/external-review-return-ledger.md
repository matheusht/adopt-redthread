# External Review Return Ledger

## Purpose

The external review return ledger tracks what came back from each external reviewer slot after distribution.

It answers one operational question:

> Which reviewer summaries are missing, incomplete, privacy-blocked, decision-follow-up-needed, or complete?

It is operational tracking only. It is not external validation until complete sanitized observation summaries are rolled into the external validation readout.

## Command

```bash
make evidence-external-review-returns
```

Default output:

```text
runs/external_review_returns/
├── external_review_return_ledger.md
└── external_review_return_ledger.json
```

Schema:

```text
adopt_redthread.external_review_return_ledger.v1
```

## Inputs

The ledger reads sanitized/generated metadata only:

- `runs/external_review_distribution/external_review_distribution_manifest.json`
- expected `reviewer_observation_summary.json` paths listed by the distribution manifest

It does **not** read filled reviewer observation markdown directly. The only acceptable path from raw reviewer answers into this flow is:

```bash
make evidence-observation-summary OBSERVATION=... OBSERVATION_OUTPUT=...
```

## What it never includes

The ledger must not include:

- raw reviewer free-form answers
- raw HAR/session material
- credentials or auth material
- request or response bodies
- source files
- staging or production write-context values
- raw boundary actor, tenant, resource, selector, credential, request, or response values

## Statuses

Ledger statuses:

- `privacy_blocked` — configured sensitive-marker audit failed in inputs, output, or embedded summary audit metadata.
- `missing_required_evidence` — the distribution manifest is missing or has the wrong schema.
- `waiting_for_returns` — at least one expected sanitized summary is missing.
- `needs_followup` — summaries exist but at least one is invalid, incomplete, or needs decision-language follow-up.
- `ready_for_external_validation_readout` — every expected reviewer slot has a complete, marker-clean sanitized summary with usable decision language.

Per-review return statuses:

- `missing_summary`
- `invalid_summary`
- `privacy_blocked`
- `incomplete_summary`
- `needs_decision_followup`
- `complete`

## Expected local state before human review

Before real external reviewers return filled observations, the expected status is:

```text
waiting_for_returns
```

That is the correct honest state. It means the distribution package may be ready, but external validation has not happened.

## Return flow

For each reviewer:

```bash
make evidence-observation-summary \
  OBSERVATION=runs/external_review_sessions/review_1/filled_reviewer_observation.md \
  OBSERVATION_OUTPUT=runs/external_review_sessions/review_1
```

Then regenerate the return ledger:

```bash
make evidence-external-review-returns
```

After all expected summaries are complete and marker-clean:

```bash
make evidence-external-validation-readout
make evidence-freshness
make evidence-readiness
make evidence-remediation-queue
```

## Non-claims

The return ledger does not prove:

- external human validation
- buyer demand
- production readiness
- boundary execution
- whole-app safety
- release approval

It does not change local bridge `approve` / `review` / `block` semantics.

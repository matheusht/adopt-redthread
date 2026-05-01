# Next Two Slices Plan

Date: 2026-05-01

## Scope

Implement only local, privacy-preserving external-review mechanics. Do not build a live boundary executor, do not run production or staging probes, do not add a new integration, and do not change `approve` / `review` / `block` semantics.

These slices follow the completed boundary result artifact and reviewer-surface integration work.

## Slice 1 — External review session batch

### Objective

Turn the sanitized external handoff into isolated per-review folders so three human reviewers can be run without sharing prior answers, repo context, or raw artifacts.

### Implemented artifacts

- `scripts/build_external_review_session_batch.py`
- `make evidence-external-review-sessions`
- `runs/external_review_sessions/external_review_session_batch.{md,json}` generated locally
- `runs/external_review_sessions/review_*/` generated locally
- `tests/test_external_review_session_batch.py`
- `docs/external-review-session-batch.md`

### Acceptance criteria

- Reads only `runs/external_review_handoff/external_review_handoff_manifest.json` and the handoff's allowed markdown artifacts.
- Copies only sanitized allowed artifacts into per-review folders.
- Creates one blank filled-observation file per reviewer and records the exact summary command for that reviewer.
- Records the rollup command for the expected summaries.
- Fails closed on configured sensitive-marker hits.
- States clearly that session folders are not validation evidence until filled observations are summarized and rolled up.
- Does not include raw HAR/session/cookie/header/body/request/response data, source files, repo context, or write-context values.

## Slice 2 — External validation readout

### Objective

Make the external validation state machine explicit: waiting for filled observations, needing more complete reviews, privacy blocked, or ready for external validation readout.

### Implemented artifacts

- `scripts/build_external_validation_readout.py`
- `make evidence-external-validation-readout`
- `runs/external_validation_readout/external_validation_readout.{md,json}` generated locally
- `runs/external_validation_readout/reviewer_validation_rollup.{md,json}` generated locally via existing rollup logic
- `tests/test_external_validation_readout.py`
- `docs/external-validation-readout.md`

### Acceptance criteria

- Reads only the external session batch manifest and sanitized `reviewer_observation_summary.json` files.
- With missing summaries, reports `waiting_for_filled_external_observations` rather than claiming validation.
- With fewer than three complete summaries, reports `needs_more_complete_external_reviews`.
- With three complete consistent sanitized summaries, reports `ready_for_external_validation_readout`.
- With configured marker hits, fails closed by default and can report `privacy_blocked` only when explicitly allowed.
- Does not copy raw reviewer answer text into the readout.
- Does not claim buyer demand, production readiness, whole-app safety, or RedThread ownership of the final bridge gate.

## Still blocked after these slices

Actual external validation is still blocked until real external reviewers fill the session observations and those observations are summarized. Boundary execution remains blocked until approved non-production context exists with safe actor scopes, selector bindings, and operator approval.

# Next Three Slices Plan

Date: 2026-05-01

## Scope

Implement only local, privacy-preserving evidence-loop work. Do not add a new integration, do not execute against production or staging, and do not change `approve` / `review` / `block` semantics.

## Slice 1 — Package sanitized external-review handoff

### Objective

Make the current reviewer packet easy to hand to an external human reviewer without accidentally including repo context or raw run material.

### Implemented artifacts

- `scripts/build_external_review_handoff.py`
- `make evidence-external-review-handoff`
- `runs/external_review_handoff/` generated locally
- `tests/test_external_review_handoff.py`
- `docs/external-human-cold-review-handoff.md`

### Acceptance criteria

- Only sanitized markdown artifacts are copied.
- Artifact hashes are recorded.
- Configured sensitive-marker audit passes.
- Handoff completeness audit passes for report/matrix.
- Manifest states this is not validation until filled observations are summarized.

## Slice 2 — Make external human validation executable, but not claimed

### Objective

Turn the human validation protocol into a repeatable command path while preserving the rule that actual external validation requires filled reviewer observations.

### Implemented behavior

The external handoff includes reviewer instructions and a manifest with:

- allowed files
- forbidden inputs
- silent-review rule
- per-review summary command
- three-review rollup command
- count rule for complete validation observations

### Acceptance criteria

- Incomplete, walked-through, or marker-hit observations are explicitly non-validation evidence.
- The target count remains three complete summaries.
- The process still uses `summarize_reviewer_observation.py` and `summarize_reviewer_validation_rollup.py` rather than copying reviewer free-form text into a rollup.

### Blocked external step

Actual external human validation is still pending. It requires real reviewers to fill observation templates from the sanitized handoff.

## Slice 3 — Tenant/user boundary execution design

### Objective

Convert the repeated reviewer ask into a safe execution design before writing any executor.

### Implemented artifacts

- `scripts/build_boundary_execution_design.py`
- `make evidence-boundary-execution-design`
- `docs/tenant-user-boundary-execution-design.md`
- `runs/boundary_execution_design/` generated locally
- `tests/test_boundary_execution_design.py`

### Contracts defined

- Approved context schema: `adopt_redthread.boundary_probe_context.v1`
- Sanitized result schema: `adopt_redthread.boundary_probe_result.v1`
- Result statuses:
  - `not_run`
  - `passed_boundary_probe`
  - `failed_boundary_probe`
  - `blocked_missing_context`
  - `auth_or_replay_failed`

### Acceptance criteria

- Design is not an executor.
- Production targets remain forbidden.
- Raw actor, tenant, resource, session, credential, request-body, response-body, and write-context values are forbidden from generated artifacts.
- Auth/replay/context failure remains separate from confirmed vulnerability language.
- Reviewed-write does not become `approve` from design alone.

## Follow-up implemented

The next two slices are now tracked in [`docs/next-two-slices-plan.md`](next-two-slices-plan.md): a boundary probe result template/validator and report/matrix/packet integration for that result artifact. Live boundary execution remains blocked until approved non-production context exists.

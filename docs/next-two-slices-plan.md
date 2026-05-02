# Next Two Slices Plan

Date: 2026-05-02

## Scope

Implement only local, privacy-preserving evidence-loop mechanics. Do not build a live boundary executor, do not run production or staging probes, do not add a new integration, and do not change `approve` / `review` / `block` semantics.

Actual external validation is still blocked until real reviewers fill observations and those observations are summarized. Boundary execution remains blocked until approved non-production context exists.

## Slice 1 — External review return ledger

### Objective

Track what came back from each external reviewer slot after distribution without reading filled observation markdown or copying free-form reviewer answers.

### Implemented artifacts

- `scripts/build_external_review_return_ledger.py`
- `make evidence-external-review-returns`
- `runs/external_review_returns/external_review_return_ledger.{md,json}` generated locally
- `tests/test_external_review_return_ledger.py`
- `docs/external-review-return-ledger.md`

### Acceptance criteria

- Reads only the external review distribution manifest and expected sanitized `reviewer_observation_summary.json` files.
- Does not read filled observation markdown directly.
- Reports ledger statuses: `waiting_for_returns`, `needs_followup`, `ready_for_external_validation_readout`, `privacy_blocked`, and `missing_required_evidence`.
- Reports per-review statuses: `missing_summary`, `invalid_summary`, `privacy_blocked`, `incomplete_summary`, `needs_decision_followup`, and `complete`.
- Emits exact follow-up commands from the distribution manifest.
- Fails closed on configured sensitive-marker hits, including embedded summary audit metadata.
- Does not include raw reviewer free-form answers or raw app/run artifacts.
- Does not claim buyer demand, production readiness, whole-app safety, boundary execution, or release approval.
- Does not change local bridge `approve` / `review` / `block` verdict semantics.

### Current local result

Before real external reviewer returns, the expected generated state is:

- `ledger_status: waiting_for_returns`
- `complete_count: 0/3`

That is the correct honest state: the session folders can be distributed, but external validation has not happened.

### Test/verification commands

```bash
python3 -m py_compile scripts/build_external_review_return_ledger.py scripts/build_evidence_remediation_queue.py
python3 -m unittest tests.test_external_review_return_ledger tests.test_evidence_remediation_queue -v
make evidence-external-review-returns
make evidence-remediation-queue
```

## Slice 2 — Boundary context intake validator

### Objective

Make the boundary-execution unblock path concrete without executing probes. Add a sanitized approved-context template and validator for future `adopt_redthread.boundary_probe_context.v1` inputs.

### Planned artifacts

- `scripts/build_boundary_probe_context_template.py` or equivalent context validator
- `make evidence-boundary-probe-context`
- `runs/boundary_probe_context/tenant_user_boundary_probe_context.template.{md,json}` generated locally
- `tests/test_boundary_probe_context.py`
- `docs/tenant-user-boundary-probe-context.md`

### Acceptance criteria

- Template records only metadata needed to prove approved non-production context exists.
- Requires operator approval metadata, non-production target classification, actor separation, tenant/user scope class, expiration, and safe execution constraints.
- Does not include raw actor IDs, tenant IDs, resource IDs, credentials, headers, cookies, request bodies, response bodies, or production write-context values.
- Validator reports missing/invalid context as blocked, not as a confirmed vulnerability.
- Does not execute probes or alter existing boundary result semantics.
- Does not change local bridge `approve` / `review` / `block` verdict semantics.

## Still blocked after Slice 1

External validation still requires real filled external reviewer observations and sanitized summaries. Boundary execution still requires approved non-production tenant/user context with safe actor scopes, selector bindings, and operator approval.

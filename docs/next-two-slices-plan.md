# Next Two Slices Plan

Date: 2026-05-02

## Scope

Implement only local, privacy-preserving evidence-loop mechanics. Do not build a live boundary executor, do not run production or staging probes, do not add a new integration, and do not change `approve` / `review` / `block` semantics.

Actual external validation is still blocked until real reviewers fill observations and those observations are summarized. Boundary execution remains blocked until approved non-production context exists.

## Slice 1 — Boundary context intake validator

### Objective

Make the boundary-execution unblock path concrete without executing probes. Add a sanitized approved-context template and validator for future `adopt_redthread.boundary_probe_context.v1` inputs.

### Implemented artifacts

- `scripts/build_boundary_probe_context.py`
- `make evidence-boundary-probe-context`
- `runs/boundary_probe_context/tenant_user_boundary_probe_context.template.{md,json}` generated locally
- `tests/test_boundary_probe_context.py`
- `docs/tenant-user-boundary-probe-context.md`

### Acceptance criteria

- Template records only metadata needed to prove approved non-production context exists.
- Requires operator approval metadata, non-production target classification, actor separation, tenant/user scope class, expiration, and safe execution constraints.
- Does not include raw actor IDs, tenant IDs, resource IDs, credentials, headers, cookies, request bodies, response bodies, or production write-context values.
- Validator reports missing/invalid context as blocked setup state, not as a confirmed vulnerability.
- Validator reports configured marker or forbidden raw-field-key hits as `privacy_blocked` or fails closed when requested.
- Does not execute probes or alter existing boundary result semantics.
- Does not change local bridge `approve` / `review` / `block` verdict semantics.

### Current local result

Before approved non-production tenant/user context exists, the expected generated state is:

- `context_status: blocked_missing_context`
- `boundary_probe_execution_authorized: false`
- `boundary_probe_executed: false`

That is the correct honest state: the unblock path is now concrete, but no probe has run.

### Test/verification commands

```bash
python3 -m py_compile scripts/build_boundary_probe_context.py scripts/build_evidence_remediation_queue.py
python3 -m unittest tests.test_boundary_probe_context tests.test_evidence_remediation_queue -v
make evidence-boundary-probe-context
make evidence-remediation-queue
```

## Slice 2 — Boundary context surfacing in readiness/remediation

### Objective

Make readiness and remediation report boundary context intake state explicitly, without treating a ready context as execution proof.

### Planned artifacts

- `scripts/build_evidence_readiness.py` boundary context component support
- `tests/test_evidence_readiness.py` coverage for missing/invalid/ready boundary context states
- `docs/evidence-readiness-ledger.md` update
- `docs/evidence-remediation-queue.md` update if new blocker/action detail is needed

### Acceptance criteria

- Readiness shows boundary context status separately from boundary probe result status.
- Missing/invalid context remains a blocker for boundary execution.
- `ready_for_boundary_probe` context does not clear the `boundary_probe_not_executed` blocker by itself.
- Privacy-blocked context fails closed through existing marker-audit behavior.
- No raw context values are read, copied, or surfaced.
- No probe is executed.
- No bridge verdict semantics change.

## Still blocked after Slice 1

External validation still requires real filled external reviewer observations and sanitized summaries. Boundary execution still requires approved non-production tenant/user context with safe actor scopes, selector bindings, operator approval, and a future executor that consumes only validated context.

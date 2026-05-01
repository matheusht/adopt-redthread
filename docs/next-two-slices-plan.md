# Next Two Slices Plan

Date: 2026-05-01

## Scope

Implement only local, privacy-preserving evidence-loop work. Do not build a live boundary executor, do not run production or staging probes, do not add a new integration, and do not change `approve` / `review` / `block` semantics.

These slices follow the previous external-review handoff and tenant/user boundary execution-design work.

## Slice 1 — Boundary probe result artifact template/validator

### Objective

Create the missing artifact that report, matrix, and reviewer handoff surfaces can consume when boundary evidence exists, without pretending that a boundary probe has run.

### Implemented artifacts

- `scripts/build_boundary_probe_result.py`
- `make evidence-boundary-probe-result`
- `runs/boundary_probe_result/tenant_user_boundary_probe_result.{md,json}` generated locally
- `tests/test_boundary_probe_result.py`
- `docs/tenant-user-boundary-probe-result.md`

### Current generated status

The default generated result is intentionally:

```text
blocked_missing_context
```

That means approved non-production boundary context is missing. It is review evidence, not a confirmed vulnerability, and not execution proof.

### Result statuses supported

- `not_run`
- `passed_boundary_probe`
- `failed_boundary_probe`
- `blocked_missing_context`
- `auth_or_replay_failed`

### Acceptance criteria

- The script is a template/validator, not an executor.
- With no observed result input, it writes an honest `blocked_missing_context` artifact.
- The artifact records only selector labels, outcome classes, status families, gate interpretation, context-readiness labels, and marker-audit results.
- It forbids raw actor, tenant, resource, credential, session, request-body, response-body, auth header, cookie, and value-preview fields.
- `failed_boundary_probe` must be a confirmed security finding; all other statuses must not be marked as confirmed security findings.
- No verdict semantics change from writing this artifact.

## Slice 2 — Surface boundary result evidence in reviewer surfaces

### Objective

Make completed boundary result evidence visible where reviewers already read evidence, while preserving the existing `tenant_user_boundary_unproven` wording when no result exists.

### Implemented surfaces

- `scripts/build_evidence_report.py`
  - adds a `## Tenant/user boundary probe result` section
  - adds a quick-read boundary result line
  - changes next-evidence wording to request approved boundary context when the result is `blocked_missing_context`
- `scripts/build_evidence_matrix.py`
  - adds a `Boundary probe result` matrix column
- `scripts/build_reviewer_packet.py`
  - includes the boundary result artifact in the packet manifest when present
  - marks it as optional in the cold-review protocol
- `scripts/build_external_review_handoff.py`
  - copies the boundary result markdown into the external handoff when present

### Acceptance criteria

- If no boundary result artifact exists, report/matrix/packet wording still says boundary evidence is absent or `tenant_user_boundary_unproven` remains driven by coverage gaps.
- If a boundary result artifact exists, report/matrix/packet surfaces show status, executed flag, selector evidence, own/cross result classes, replay failure category, gate interpretation, and marker audit status.
- A result artifact does not silently turn reviewed-write evidence into `approve`.
- Raw values remain local/ignored and are not copied into reviewer artifacts.

## Still blocked after these slices

Boundary execution itself remains blocked until approved non-production context exists with safe actor scopes, selector bindings, and operator approval. The next implementation should still stop before any executor unless that context is explicitly supplied and approved.

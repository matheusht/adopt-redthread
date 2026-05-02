# Tenant/User Boundary Probe Context Intake

`make evidence-boundary-probe-context` writes a sanitized approved-context template and intake validation artifact for future tenant/user boundary probe execution.

This is not a probe executor. It does not resolve actor/resource values, does not send traffic, and does not change `approve` / `review` / `block` verdict semantics.

## Outputs

Generated locally under ignored `runs/`:

- `runs/boundary_probe_context/tenant_user_boundary_probe_context.template.json`
- `runs/boundary_probe_context/tenant_user_boundary_probe_context.template.md`

The schema label is:

- `adopt_redthread.boundary_probe_context.v1`

## Statuses

- `blocked_missing_context` — no sanitized approved context metadata was supplied.
- `blocked_invalid_context` — context metadata exists, but required approval/scope/safety fields are missing or invalid.
- `privacy_blocked` — configured marker or forbidden raw-field-key checks failed.
- `ready_for_boundary_probe` — sanitized context metadata is complete enough for a future executor to consider; the probe still has not run.

## Required sanitized metadata

The context must describe only labels and references:

- non-production target classification
- environment label and base URL label
- `production=false`
- explicit approval for boundary probing
- allowed execution mode
- own-scope and cross-scope actor labels
- actor separation confirmation
- tenant/user scope class
- selector metadata and own/cross value-reference labels
- operator approval label, approval timestamp, expiration timestamp, and scope note
- safe execution constraints

## Forbidden content

Do not put raw actor, tenant, resource, credential, session, auth-header, request, response, or write-context values in this artifact.

The validator fails closed on configured marker hits and forbidden raw-field keys. A privacy block is packaging/safety state, not a confirmed vulnerability.

## Command

```bash
make evidence-boundary-probe-context
```

To validate an explicit sanitized context file without executing a probe:

```bash
python3 scripts/build_boundary_probe_context.py \
  --context /path/to/sanitized_boundary_probe_context.json \
  --fail-on-marker-hit
```

## Non-claims

- A ready context is not boundary execution proof.
- Missing or invalid context is not a confirmed security finding.
- This artifact does not authorize production writes.
- This artifact does not approve release.
- This artifact does not change bridge verdict semantics.

# Tenant/User Boundary Probe Context Request

`make evidence-boundary-context-request` writes a sanitized request package for the approved non-production boundary context metadata needed before any future tenant/user boundary probe can be considered.

This is a coordination/checklist artifact. It does not execute probes, resolve values, contact systems, approve release, or change bridge verdict semantics.

## Command

```bash
make evidence-boundary-context-request
```

Default output:

```text
runs/boundary_probe_context_request/
├── tenant_user_boundary_probe_context_request.md
└── tenant_user_boundary_probe_context_request.json
```

Schema:

```text
adopt_redthread.boundary_probe_context_request.v1
```

## Input

The request builder reads only the sanitized boundary context intake artifact:

```text
runs/boundary_probe_context/tenant_user_boundary_probe_context.template.json
```

If approved context exists locally, validate it through the intake builder first:

```bash
make evidence-boundary-probe-context BOUNDARY_CONTEXT=path/to/sanitized_context.json
make evidence-boundary-context-request
```

The context file path should be local/ignored and must contain sanitized labels and references only.

## Statuses

- `missing_required_evidence` — the context intake artifact is missing or invalid; regenerate the plan/design/context template first.
- `ready_to_request_context` — the intake exists, but approved context metadata is missing or invalid.
- `context_ready` — sanitized context intake reports `ready_for_boundary_probe`; this is still not execution proof.
- `privacy_blocked` — configured sensitive markers or forbidden raw-field keys were detected.

## What the request includes

The request package may include:

- required context schema
- source context status
- missing condition labels
- validation blocker codes/details
- sanitized context template shape
- forbidden-input list
- validation commands
- acceptance criteria
- non-claims

## What it must never include

The request package must not include:

- raw actor IDs
- raw tenant IDs
- raw resource IDs
- credentials or session values
- auth headers or cookies
- request or response bodies
- production URLs or production write-context values
- reviewer free-form answers

Configured marker hits and forbidden raw-field-key hits fail closed when `--fail-on-marker-hit` is used.

## Non-claims

The request package does not prove:

- boundary execution
- a confirmed security finding
- release approval
- external human validation
- production readiness
- whole-app safety

A `context_ready` request status only means the sanitized context metadata is complete enough for a future approved non-production executor path to be considered. A separate executor and sanitized boundary result would still be required.

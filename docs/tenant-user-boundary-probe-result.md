# Tenant/User Boundary Probe Result Artifact

This document describes the local boundary result artifact added after the boundary probe plan and execution design.

## Purpose

The artifact gives reviewer-facing surfaces a stable place to read tenant/user boundary evidence without adding a live executor.

It answers:

- Was a tenant/user boundary probe actually executed?
- Which structural selector was used?
- Did own-scope control and cross-scope probe produce interpretable outcome classes?
- Was the result a pass, fail, missing-context block, auth/replay failure, or not-run state?
- Is the result a confirmed security finding?

## Command

```bash
make evidence-boundary-probe-result
```

Default inputs:

```text
runs/boundary_probe_plan/tenant_user_boundary_probe_plan.json
runs/boundary_execution_design/tenant_user_boundary_execution_design.json
```

Default outputs:

```text
runs/boundary_probe_result/tenant_user_boundary_probe_result.md
runs/boundary_probe_result/tenant_user_boundary_probe_result.json
```

`runs/` remains ignored/local.

## Current honest status

With no approved non-production boundary context and no executor, the default output is:

```text
result_status: blocked_missing_context
boundary_probe_executed: false
gate_decision: review
confirmed_security_finding: false
```

This is intentional. Missing approved context is not a confirmed vulnerability and does not prove boundary enforcement. It tells the reviewer exactly what is still needed.

## Schema

Schema version:

```text
adopt_redthread.boundary_probe_result.v1
```

Required result fields:

- `schema_version`
- `result_status`
- `boundary_probe_executed`
- `selector_evidence`
- `own_scope_result_class`
- `cross_scope_result_class`
- `http_status_family`
- `replay_failure_category`
- `gate_decision`
- `confirmed_security_finding`
- `context_readiness`
- `interpretation`
- `configured_sensitive_marker_check`

Allowed statuses:

- `not_run`
- `passed_boundary_probe`
- `failed_boundary_probe`
- `blocked_missing_context`
- `auth_or_replay_failed`

Allowed result classes:

- `allowed`
- `denied`
- `no_data_exposed`
- `blocked`
- `not_run`
- `unknown`

Allowed status families:

- `2xx`
- `3xx`
- `4xx`
- `5xx`
- `not_applicable`
- `unknown`

## Privacy rules

The artifact may contain:

- selector name
- selector class
- selector location
- operation ID
- path template
- outcome classes
- status family
- replay/auth/context failure category
- bounded context-readiness labels

The artifact must not contain raw:

- actor IDs
- tenant IDs
- resource IDs
- credential values
- session values
- auth headers
- cookies
- request bodies
- response bodies
- write-context values

The script fails closed on the configured sensitive-marker set and on forbidden raw-field keys in observed result input.

## Decision semantics

| Status | Meaning | Gate interpretation |
|---|---|---|
| `not_run` | No boundary execution evidence exists. | Keep `tenant_user_boundary_unproven` wording. |
| `passed_boundary_probe` | Own-scope control worked and cross-scope probe was denied or exposed no data. | May remove the boundary gap later, but does not automatically approve write-capable paths. |
| `failed_boundary_probe` | Cross-scope probe was allowed where denial/no exposure was expected. | Block; this must be marked as a confirmed security finding. |
| `blocked_missing_context` | Approved target, actor scope, selector binding, auth context, or write context is missing. | Review; not a confirmed vulnerability. |
| `auth_or_replay_failed` | The probe could not be interpreted because auth, replay, host, environment, or policy continuity failed. | Review/block according to existing policy; not a confirmed vulnerability by itself. |

## Surface integration

When present, the result is surfaced in:

- `runs/reviewed_write_reference/evidence_report.md`
- `runs/evidence_matrix/evidence_matrix.md`
- `runs/reviewer_packet/reviewer_packet.md`
- `runs/external_review_handoff/tenant_user_boundary_probe_result.md`

When absent, these surfaces preserve the current wording: boundary evidence is absent and `tenant_user_boundary_unproven` remains driven by coverage gaps.

## Non-goals

This artifact does not:

- execute a boundary probe
- approve production or staging writes
- read raw context values
- change the local gate verdict by itself
- upstream a RedThread enforcement contract
- replace external reviewer validation

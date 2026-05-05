# Approved Context Replay v1

Approved Context Replay v1 is the next narrow engine slice after the OWASP Shop lesson capture.

It addresses the specific gap exposed by OWASP: the bridge can say `context_ready`, but it needs a privacy-preserving way to turn approved non-production runtime context into sanitized endpoint execution proof.

## Decision

Build a small project-wide replay/proof primitive, not a broad scanner and not an OWASP-only hack.

The primitive answers one bounded question:

> Given one live-plan case plus approved non-production runtime context and explicit operator execution approval, was that one endpoint/workflow case executed, and what sanitized result class was observed?

## Non-goals

This is not:

- a production executor
- an autonomous exploitation scanner
- a crawler
- a release gate override
- a replacement for external validation
- boundary execution proof unless a boundary replay actually executes
- permission to run staging/production writes
- permission to persist cookies, auth headers, request bodies, response bodies, or raw target URLs

## State model

The engine must keep these states separate:

1. `context_ready`
2. `execution_approved`
3. `executed`
4. `validated`
5. `release_approved`

Rules:

- `context_ready` is not execution proof.
- `execution_approved` is not execution proof.
- `executed` is not validation.
- `validated` is not release approval.
- Safe HTTP `4xx` rejection is rejection evidence, not approval.
- RedThread evidence never overrides the local bridge `approve` / `review` / `block` gate.

## Artifacts

Default output directory:

```text
runs/approved_context_replay/
```

Generated files:

```text
approved_context_replay_plan.json
approved_context_replay_result.json
approved_context_replay.md
```

Schema versions:

```text
adopt_redthread.approved_context_replay_plan.v1
adopt_redthread.approved_context_replay_result.v1
adopt_redthread.approved_context_replay_execution_approval.v1
```

## Command: plan / not-run mode

Plan-only mode is the safe default. It writes a sanitized plan and a result with `executed: false`.

```bash
make evidence-approved-context-replay \
  APPROVED_REPLAY_ATTACK_PLAN=runs/owasp_shop/live_attack_plan.json \
  APPROVED_REPLAY_CASE=post_api_Users \
  APPROVED_REPLAY_OUTPUT=runs/owasp_shop/approved_context_replay/post_api_Users
```

Expected default result:

```text
context_ready: false unless the matching approved context is supplied
execution_approved: false unless an execution approval artifact is supplied
execute_requested: false
executed: false
result_class: not_run
release_gate_override: false
confirmed_security_finding: false
```

## Command: execution approval request

After plan/not-run mode, generate the sanitized approval request and false-by-default local template:

```bash
make evidence-approved-context-replay-approval-request \
  APPROVED_REPLAY_OUTPUT=runs/owasp_shop/approved_context_replay/post_api_Users_context_checked
```

Generated files:

```text
execution_approval_request.json
execution_approval_request.md
execution_approval.local.template.json
```

The request status is:

- `blocked_until_runtime_context_ready` when the approved runtime context is not ready
- `ready_to_request_execution_approval` when context is ready but explicit execution approval is absent
- `execution_approval_present_not_executed` when approval exists but execution has not run
- `already_executed` when the replay result already contains execution proof

The template is intentionally false by default. It is not approval until an operator reviews it and sets all approval booleans to `true` in a local ignored approval file.

## Command: execution mode

Execution mode requires all of these:

- approved non-production runtime context
- explicit sanitized execution approval artifact
- `APPROVED_REPLAY_EXECUTE=1`
- explicit matching case ID and execution mode in the approval artifact
- non-empty sanitized approval label
- existing live-replay guardrails passing

Wildcard approval scope is rejected. Approved Context Replay v1 is intentionally one endpoint/workflow case at a time.

Example shape:

```bash
make evidence-approved-context-replay \
  APPROVED_REPLAY_ATTACK_PLAN=runs/owasp_shop/live_attack_plan.json \
  APPROVED_REPLAY_CASE=post_api_Users \
  APPROVED_REPLAY_OUTPUT=runs/owasp_shop/approved_context_replay/post_api_Users \
  APPROVED_REPLAY_WRITE_CONTEXT=runs/owasp_shop/staging_write_context.json \
  APPROVED_REPLAY_EXECUTION_APPROVAL=runs/owasp_shop/approved_context_replay/execution_approval.local.json \
  APPROVED_REPLAY_EXECUTE=1
```

Do not run this command until the operator has approved a non-production execution window. The approval artifact is sanitized metadata; it is not the raw auth/write context.

## Execution approval artifact

A minimal sanitized approval artifact looks like:

```json
{
  "schema_version": "adopt_redthread.approved_context_replay_execution_approval.v1",
  "approved": true,
  "approved_non_production_scope": true,
  "operator_execution_approval_present": true,
  "allowed_case_ids": ["post_api_Users"],
  "allowed_execution_modes": ["live_reviewed_write_staging"],
  "approval_label": "approved_non_production_window_label"
}
```

Do not include cookies, auth headers, request bodies, response bodies, raw URLs, tenant IDs, actor IDs, resource IDs, credentials, or reviewer free-form answers in this approval artifact. Keep `allowed_case_ids` and `allowed_execution_modes` explicit; empty lists or `"*"` wildcards are rejected.

## Result classes

Allowed result classes:

- `not_run` — no execution was attempted
- `blocked` — execution was requested but guardrails, context, approval, network, or replay policy blocked interpretation
- `safe_success` — endpoint replay completed with a safe success class
- `safe_rejection` — endpoint replay produced a safe rejection class, usually HTTP `4xx`
- `potential_finding` — reserved for future confirmed-observation flows; current v1 does not auto-promote findings

Current v1 always sets:

```text
confirmed_security_finding: false
release_gate_override: false
decision_semantics_changed: false
```

The result also includes an `approval_scope` summary. It reports only sanitized booleans/counts, not raw approval text or runtime values. This lets reviewers distinguish missing approval, broad/wildcard approval, mismatched case/mode approval, and exact per-case approval without exposing secrets.

A potential issue becomes a confirmed finding only after a future judge/validation step confirms actual observed policy violation from sanitized evidence.

## Privacy policy

Generated artifacts may contain:

- case ID
- method class
- path template
- execution mode
- approval mode
- side-effect risk label
- query/body field counts
- execution booleans
- result class
- HTTP status family
- replay failure category
- sanitized approval-scope booleans and counts, such as approval supplied, explicit case scope present, requested case in scope, and wildcard rejected

Generated artifacts must not contain raw:

- target URLs
- cookies
- auth headers
- credential/session values
- request bodies
- response bodies
- response headers
- source files
- actor IDs
- tenant IDs
- resource IDs
- write-context values
- reviewer free-form answers

The script audits generated artifacts for configured sensitive markers and forbidden raw-field keys.

## Readiness/remediation integration

Approved Context Replay v1 can now be indexed by the evidence readiness ledger without making replay proof mandatory for every run:

```bash
make evidence-readiness \
  EVIDENCE_APPROVED_REPLAY_RESULT=runs/approved_context_replay/approved_context_replay_result.json
```

When the supplied result has `executed: false`, readiness adds:

```text
approved_context_replay_not_executed
```

The remediation queue converts that into `complete_approved_context_replay_execution` and keeps the next action specific to the current state:

- context absent -> supply approved non-production runtime context locally
- context ready but approval absent -> generate the sanitized approval request and wait
- approval present but not executed -> execute only with the explicit execute flag in the approved non-production window

This integration is still only evidence accounting. It does not execute endpoints, validate findings, approve release, or mutate bridge gate semantics.

## Why this is the right next slice

OWASP showed that more packaging is not the core missing piece. The missing piece is controlled execution proof:

```text
approved runtime context
  -> one guarded endpoint replay
  -> sanitized observed-result artifact
  -> readiness/remediation can reason about executed vs not executed
  -> local gate semantics remain unchanged
```

This makes the engine less vague without turning it into a broad exploit scanner.

## OWASP status after this change

This engine slice does not change the current OWASP verdict by itself:

- release decision: `block`
- boundary context: `ready_for_boundary_probe`
- boundary probe executed: `false`
- formal external validation: `not_claimed`

OWASP can use this primitive later only after a separate approved non-production execution window exists.

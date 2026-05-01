# RedThread Evidence Contract Proposal

Schema version: `redthread.evidence_contract_proposal.v0`

Status: `proposal_only_not_upstreamed`

## Purpose

Define the smallest generic evidence shape RedThread should own so adapters can supply sanitized workflow, replay, attack, and promotion evidence without app-specific ingestion names.

## Ownership split

RedThread should own:

- generic evidence schema
- replay and dry-run evidence summaries
- promotion-gate recommendation semantics
- attack brief and rerun trigger vocabulary

Adapters should own:

- source ingestion
- source-specific fixture normalization
- local safety policy for approved execution context
- mapping source artifacts into the generic evidence contract

## Required generic sections

### evidence_envelope

- Owner: `redthread`
- Fields: `schema_version,run_id,input_family,operation_count,workflow_count,artifact_manifest`
- Reason: Pin what was tested and which sanitized artifacts were reviewed.

### workflow_evidence

- Owner: `redthread`
- Fields: `ordered_operations,workflow_classes,successful_workflow_count,blocked_workflow_count,response_binding_summary,binding_audit_summary`
- Reason: Separate actual workflow proof from fixture-only or planning-only evidence; ordered_operations should carry sanitized sequence index, operation id, action class, method class, path template, and binding/input role labels.

### attack_context_summary

- Owner: `redthread`
- Fields: `tool_action_schemas,action_class_counts,auth_model_label,data_sensitivity_tags,boundary_selector_classes,dispatch_selector_classes,field_role_summary,targeted_missing_context_questions`
- Reason: Give attack generation the minimum structural context needed for ownership, dispatch, auth, and data-sensitivity probes; tool_action_schemas should include action names/classes, required/optional parameter names, field roles, binding targets, and boundary-relevant field classes only.

### replay_and_auth_diagnostics

- Owner: `redthread`
- Fields: `replay_passed,dry_run_executed,auth_delivery_label,approved_auth_context_required,approved_write_context_required,replay_failure_category`
- Reason: Explain auth/replay/context blocks without exposing credentials or sessions.

### promotion_recommendation

- Owner: `redthread`
- Fields: `recommendation,decision_reason_category,confirmed_security_finding,coverage_label,coverage_gaps,trusted_evidence,not_proven`
- Reason: Move generic approve/review/block recommendation semantics toward RedThread while keeping source ingestion outside the schema.

### next_evidence_guidance

- Owner: `redthread`
- Fields: `top_targeted_probe,next_evidence_needed,rerun_triggers,reviewer_action`
- Reason: Tell a reviewer what to do next without requiring raw artifacts or repository knowledge.

## Promotion recommendation semantics

- Allowed values: `approve,review,block`
- `approve`: ship candidate only for the tested evidence envelope
- `review`: human review/change checkpoint before ship
- `block`: do not ship from this run until blockers are resolved

Must not:

- treat replay/auth/context failure as a confirmed vulnerability
- turn write-capable workflows into approve without explicit safe context and review policy
- claim whole-application safety from one evidence envelope

## Privacy rules

- schema carries structural metadata, counts, labels, classes, and sanitized explanations only
- schema does not carry raw headers, cookies, sessions, request bodies, response bodies, secrets, or captured values
- artifact manifests may carry hashes and line/byte counts for sanitized artifacts

## Acceptance tests

- consumer can explain why a run is approve/review/block without raw artifacts
- consumer can distinguish confirmed finding, auth/replay/context failure, and insufficient evidence
- consumer can identify next evidence to collect and rerun triggers
- schema contains no source-specific ingestion field names

## Non-goals

- new integration plumbing
- live-write expansion
- broad scanner wrapper
- full secret scanner
- upstream migration before reviewer comprehension is proven

## Configured sensitive marker check

- Passed: `True`
- Marker hits: `0`
- Marker set: `configured_sensitive_marker_set` (`6` configured strings)

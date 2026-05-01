# Tenant/User Boundary Execution Design

This design may contain selector names, classes, locations, operation IDs, path templates, outcome classes, and status families. It must not contain raw actor IDs, tenant IDs, resource IDs, session material, credential values, request/response bodies, or write-context values.

## Status

- Design status: `executor_not_implemented`
- Implementation gate: `do_not_execute_until_approved_non_production_context_exists`
- Source probe plan: `runs/boundary_probe_plan/tenant_user_boundary_probe_plan.json`
- This is not an executor and is not release validation by itself.

## Selector scope from current evidence

- Boundary selectors: `3`
- Selector classes: `resource:3`
- Selector locations: `body_field:3`
- Reason categories: `resource_field_selector`
- Operation IDs: `op_004_post_api_chat`
- Path templates: `/api/chat`

## Approved context contract

- Schema: `adopt_redthread.boundary_probe_context.v1`
- Storage policy: `local_ignored_file_only_never_checked_in`
- Required top-level fields: `schema_version,target_environment,execution_mode,actor_scopes,selector_bindings,operator_approval`
- Target environment required fields: `environment_label,base_url_label,production,approved_for_boundary_probe`
- Target rules: `production must be false,approved_for_boundary_probe must be true,base_url_label must be a label, not a raw URL containing credentials or query values`
- Execution modes: `safe_read_replay,reviewed_non_production_workflow`
- Write rule: write-capable paths require the existing approved write-context gate and remain review until evidence is captured
- Actor scope labels: `own_scope,cross_scope`
- Actor value rule: store raw actor, tenant, auth, and resource values only in the local approved context; generated evidence may reference labels only
- Selector binding fields: `selector_name,selector_class,selector_location,operation_id,path_template,own_scope_value_ref,cross_scope_value_ref`
- Selector value-ref rule: value_ref points to approved local context entries; generated artifacts never copy resolved values
- Operator approval fields: `approved_by,approved_at,scope_note`

## Execution flow to implement later

1. **load_approved_context**
   - Records: `context_schema_version,target_environment_label,execution_mode`
   - Blocks on: `missing_context,production_target,unapproved_target,missing_actor_scopes`
2. **select_boundary_case**
   - Selector hint: `{"operation_id": "op_004_post_api_chat", "path_template": "/api/chat", "selector_class": "resource", "selector_location": "body_field", "selector_name": "chatid"}`
   - Records: `selector_name,selector_class,selector_location,operation_id,path_template`
   - Blocks on: `missing_selector_binding,unsafe_selector_mapping`
3. **run_own_scope_control**
   - Purpose: prove the workflow can access the actor's own resource or tenant scope before cross-scope interpretation
   - Records: `own_scope_result_class,own_scope_status_family,own_scope_replay_failure_category`
   - Blocks on: `auth_or_replay_failed,own_scope_control_failed`
4. **run_cross_scope_probe**
   - Purpose: attempt the same structural operation against a different actor or tenant selector reference and expect denial or no data exposure
   - Records: `cross_scope_result_class,cross_scope_status_family,cross_scope_replay_failure_category`
   - Blocks on: `auth_or_replay_failed`
5. **write_sanitized_result**
   - Records: `result_status,gate_decision,confirmed_security_finding,sanitized_notes`
   - Blocks on: `configured_sensitive_marker_hit`

## Boundary result contract

- Schema: `adopt_redthread.boundary_probe_result.v1`
- Allowed statuses: `not_run,passed_boundary_probe,failed_boundary_probe,blocked_missing_context,auth_or_replay_failed`
- Required fields: `schema_version,result_status,boundary_probe_executed,selector_evidence,own_scope_result_class,cross_scope_result_class,http_status_family,replay_failure_category,gate_decision,confirmed_security_finding,configured_sensitive_marker_check`
- Selector evidence fields: `selector_name,selector_class,selector_location,operation_id,path_template`
- Allowed result classes: `allowed,denied,no_data_exposed,blocked,not_run,unknown`
- HTTP status family examples: `2xx,3xx,4xx,5xx,not_applicable,unknown`
- Raw-value fields forbidden: `actor_id,tenant_id,resource_id,credential_value,session_value,request_body,response_body`

## Decision mapping

### `not_run`

- Meaning: no boundary execution evidence exists
- Gate effect: keep tenant_user_boundary_unproven wording
- Confirmed security finding: `False`

### `passed_boundary_probe`

- Meaning: own-scope control worked and cross-scope probe was denied or exposed no data
- Gate effect: may remove tenant_user_boundary_unproven from the evidence gaps, but does not automatically approve write-capable paths
- Confirmed security finding: `False`

### `failed_boundary_probe`

- Meaning: cross-scope probe was allowed where denial/no-exposure was expected
- Gate effect: block until fixed or disproven with stronger approved evidence
- Confirmed security finding: `True`

### `blocked_missing_context`

- Meaning: approved target, actor scope, selector binding, auth context, or write context was missing
- Gate effect: review; missing context is not a confirmed vulnerability
- Confirmed security finding: `False`

### `auth_or_replay_failed`

- Meaning: the probe could not be interpreted because auth, replay, host, environment, or policy continuity failed
- Gate effect: review or block depending on existing gate policy; not a confirmed vulnerability by itself
- Confirmed security finding: `False`

## Privacy and safety invariants

- Generated artifacts never include raw actor, tenant, resource, credential, session, request-body, or response-body values.
- Production targets are rejected before execution.
- Write-capable paths require the existing approved non-production write-context gate.
- Own-scope control must run before cross-scope results are interpreted.
- Auth/replay/context failures are not labeled as confirmed security findings.
- The local bridge owns approve/review/block until RedThread has a validated generic enforcement contract.

## Blocked until

- external human cold-review validation confirms reviewers understand current evidence and gaps
- approved non-production target with two safe actor scopes is supplied
- approved context uses value references rather than generated-artifact raw values
- boundary result artifact parser and marker audit exist
- report/matrix wording is updated to consume boundary result evidence without changing verdict semantics

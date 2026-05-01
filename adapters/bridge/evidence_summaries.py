from __future__ import annotations

from typing import Any

AUTH_OR_CONTEXT_REASONS = {"missing_auth_context", "missing_write_context", "auth_header_family_mismatch"}
BINDING_REASONS = {"binding_review_required", "response_binding_missing", "response_binding_target_missing"}
SECRET_FIELD_HINTS = {"token", "secret", "password", "cookie", "session", "key", "credential"}
USER_FIELD_HINTS = {"user", "profile", "account", "owner", "member", "customer", "actor"}
TENANT_FIELD_HINTS = {"tenant", "org", "organization", "workspace", "company", "business"}
RESOURCE_FIELD_HINTS = {"chat", "conversation", "thread", "project", "document", "file", "order", "report", "resource", "memory"}
DISPATCH_FIELD_HINTS = {"action", "path", "function", "operation", "tool", "route", "handler", "procedure"}
MESSAGE_FIELD_HINTS = {"message", "msg", "chat", "prompt", "content", "body", "comment", "conversation", "system"}


def select_campaign_strategy(fixture: dict[str, Any]) -> dict[str, Any]:
    """Select a small deterministic RedThread dry-run strategy from sanitized fixture structure."""

    fields = _fixture_fields(fixture)
    candidates = {str(value) for value in fixture.get("candidate_attack_types", [])}
    dispatch_fields = _matching_fields(fields, DISPATCH_FIELD_HINTS)
    secret_fields = _matching_fields(fields, SECRET_FIELD_HINTS)
    user_fields = _matching_fields(fields, USER_FIELD_HINTS)
    tenant_fields = _matching_fields(fields, TENANT_FIELD_HINTS)
    resource_fields = _matching_fields(fields, RESOURCE_FIELD_HINTS)
    message_fields = _matching_fields(fields, MESSAGE_FIELD_HINTS)
    action_counts = {_fixture_action_class(fixture): 1}
    sensitivity_tags = _fixture_sensitivity_tags(fixture, fields, secret_fields, message_fields)
    risk_themes = _risk_themes(
        dispatch_fields,
        user_fields,
        tenant_fields,
        resource_fields,
        secret_fields,
        action_counts,
        sensitivity_tags,
    )

    if dispatch_fields:
        rubric_name = "authorization_bypass"
    elif message_fields or "prompt_injection" in candidates:
        rubric_name = "prompt_injection"
    elif secret_fields or "data_exfiltration" in candidates or "secret_like" in sensitivity_tags:
        rubric_name = "sensitive_info"
    elif user_fields or tenant_fields or resource_fields or "authorization_bypass" in candidates:
        rubric_name = "authorization_bypass"
    else:
        rubric_name = "authorization_bypass"

    algorithm = "crescendo" if rubric_name == "prompt_injection" else "tap" if fixture.get("replay_class") == "sandbox_only" else "pair"
    probe = _top_probe(dispatch_fields, user_fields, tenant_fields, resource_fields, secret_fields, action_counts)
    return {
        "rubric_name": rubric_name,
        "algorithm": algorithm,
        "risk_themes": risk_themes,
        "rubric_selection_rationale": rubric_rationale(rubric_name, risk_themes, probe),
        "top_targeted_probe": probe,
        "targeted_questions": targeted_missing_context_questions(risk_themes),
    }


def build_decision_reason_summary(
    gate: dict[str, Any],
    summary: dict[str, Any],
    *,
    live_workflow: dict[str, Any] | None = None,
    live_safe_replay: dict[str, Any] | None = None,
    redthread: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = str(gate.get("decision", summary.get("gate_decision", "unknown")))
    blockers = [str(item) for item in gate.get("blockers", [])]
    warnings = [str(item) for item in gate.get("warnings", [])]
    reasons = _reason_counts(summary, live_workflow)
    live_safe_failures = _live_safe_failure_present(live_safe_replay)
    redthread_failed = redthread is not None and not bool(redthread.get("passed", summary.get("redthread_replay_passed", False)))

    category = "unknown"
    primary_reason = "no_specific_reason"
    confirmed_security_finding = False

    reason_keys = set(reasons)
    if decision == "approve":
        category = "approved_clean_evidence"
        primary_reason = "no_blockers_or_warnings"
    elif decision == "review":
        if "manual_review_required_for_write_paths" in warnings:
            category = "manual_review_required_for_write_paths"
            primary_reason = "write_paths_present"
        else:
            category = "review_required"
            primary_reason = warnings[0] if warnings else "review_warning_present"
    elif redthread_failed or "redthread_replay_verdict_failed" in blockers:
        category = "redthread_replay_failed"
        primary_reason = "redthread_replay_verdict_failed"
    elif reason_keys & AUTH_OR_CONTEXT_REASONS:
        category = "auth_or_context_blocked"
        primary_reason = _first_reason(reason_keys, AUTH_OR_CONTEXT_REASONS)
    elif live_safe_failures or any(key.startswith("http_status_") for key in reason_keys):
        category = "auth_or_replay_failed"
        primary_reason = _first_http_or("live_replay_failure", reason_keys)
    elif reason_keys & BINDING_REASONS:
        category = "binding_or_workflow_context_blocked"
        primary_reason = _first_reason(reason_keys, BINDING_REASONS)
    elif "sandbox_only_items_present" in blockers:
        category = "sandbox_only_blocked"
        primary_reason = "sandbox_only_items_present"
    elif blockers:
        category = "blocked_without_confirmed_finding"
        primary_reason = blockers[0]
    else:
        category = "insufficient_decision_detail"

    return {
        "decision": decision,
        "category": category,
        "primary_reason": primary_reason,
        "confirmed_security_finding": confirmed_security_finding,
        "blockers": blockers,
        "warnings": warnings,
        "workflow_reason_counts": reasons,
        "explanation": _decision_explanation(category),
    }


def build_coverage_summary(
    summary: dict[str, Any],
    *,
    live_workflow: dict[str, Any] | None = None,
    live_safe_replay: dict[str, Any] | None = None,
    app_context_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    app_context_summary = app_context_summary or summary.get("app_context_summary", {}) or {}
    live_workflow_executed = bool(summary.get("live_workflow_replay_executed", False)) or bool(live_workflow)
    live_safe_executed = bool(summary.get("live_safe_replay_executed", False)) or bool(live_safe_replay)
    redthread_replay = bool(summary.get("redthread_replay_passed", False))
    redthread_dryrun = bool(summary.get("redthread_dryrun_executed", False))
    successful_workflows = int(_value_from(summary, live_workflow, "live_workflow_replay_count", "successful_workflow_count", 0))
    blocked_workflows = int(_value_from(summary, live_workflow, "live_workflow_blocked_count", "blocked_workflow_count", 0))
    binding = summary.get("live_workflow_binding_application_summary", {}) or {}
    applied_bindings = int(binding.get("applied_response_binding_count", 0))
    planned_bindings = int(binding.get("planned_response_binding_count", binding.get("declared_response_binding_count", 0)))
    boundary_count = int(app_context_summary.get("candidate_boundary_selector_count", 0)) or (
        int(app_context_summary.get("candidate_user_field_count", 0))
        + int(app_context_summary.get("candidate_tenant_field_count", 0))
        + int(app_context_summary.get("candidate_resource_field_count", 0))
        + int(app_context_summary.get("candidate_route_param_count", 0))
    )
    reason_counts = summary.get("live_workflow_reason_counts", {}) or (live_workflow or {}).get("reason_counts", {}) or {}

    gaps: list[str] = []
    if not live_workflow_executed and not live_safe_executed:
        gaps.append("no_live_or_workflow_replay")
    if live_workflow_executed and blocked_workflows:
        gaps.append("workflow_blocked")
    if planned_bindings and applied_bindings < planned_bindings:
        gaps.append("bindings_not_fully_applied")
    if boundary_count == 0 or not bool(summary.get("tenant_boundary_probe_executed", False)):
        gaps.append("tenant_user_boundary_unproven")
    if reason_counts and (set(reason_counts) & AUTH_OR_CONTEXT_REASONS or any(str(key).startswith("http_status_") for key in reason_counts)):
        gaps.append("auth_or_replay_blocked")

    if live_workflow_executed and successful_workflows > 0 and not blocked_workflows:
        label = "strong_workflow_coverage"
    elif "auth_or_replay_blocked" in gaps:
        label = "auth_or_replay_blocked"
    elif not live_workflow_executed and not live_safe_executed and (redthread_replay or redthread_dryrun):
        label = "weak_fixture_or_dryrun_only"
    elif live_safe_executed:
        label = "live_safe_replay_coverage"
    else:
        label = "planning_only_or_unknown"

    return {
        "label": label,
        "fixture_count": int(summary.get("fixture_count", 0)),
        "redthread_replay_passed": redthread_replay,
        "redthread_dryrun_executed": redthread_dryrun,
        "live_safe_replay_executed": live_safe_executed,
        "live_workflow_replay_executed": live_workflow_executed,
        "successful_workflow_count": successful_workflows,
        "blocked_workflow_count": blocked_workflows,
        "planned_response_binding_count": planned_bindings,
        "applied_response_binding_count": applied_bindings,
        "tenant_user_boundary_candidate_count": boundary_count,
        "tenant_user_boundary_probed": bool(summary.get("tenant_boundary_probe_executed", False)),
        "coverage_gaps": sorted(dict.fromkeys(gaps)),
    }


def build_auth_diagnostics_summary(
    summary: dict[str, Any],
    *,
    live_workflow: dict[str, Any] | None = None,
    live_safe_replay: dict[str, Any] | None = None,
    app_context_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize auth/replay continuity using structural evidence only."""

    app_context_summary = app_context_summary or summary.get("app_context_summary", {}) or {}
    requirement_summary = summary.get("live_workflow_requirement_summary", {}) or (live_workflow or {}).get("workflow_requirement_summary", {}) or {}
    reason_counts = summary.get("live_workflow_reason_counts", {}) or (live_workflow or {}).get("reason_counts", {}) or {}
    failure_classes = summary.get("live_workflow_failure_class_summary", {}) or (live_workflow or {}).get("workflow_failure_class_summary", {}) or {}
    result_counts = _auth_applied_result_counts(live_workflow, live_safe_replay)
    status_counts = _http_status_counts(live_workflow, live_safe_replay)
    error_counts = _result_error_counts(live_workflow, live_safe_replay)
    required_header_counts = requirement_summary.get("required_header_family_counts", {}) if isinstance(requirement_summary.get("required_header_family_counts", {}), dict) else {}
    auth_families = sorted(dict.fromkeys([*app_context_summary.get("auth_header_families", []), *required_header_counts.keys()]))
    auth_required = bool(app_context_summary.get("requires_approved_auth_context", False)) or bool(requirement_summary.get("approved_auth_context_required_count", 0))
    write_required = bool(app_context_summary.get("requires_approved_write_context", False)) or bool(requirement_summary.get("approved_write_context_required_count", 0))
    auth_supplied = bool(summary.get("live_workflow_used_auth_context", False) or summary.get("live_safe_replay_used_auth_context", False) or (live_workflow or {}).get("auth_context_used", False) or (live_safe_replay or {}).get("auth_context_used", False))
    write_supplied = bool(summary.get("live_workflow_used_write_context", False) or summary.get("live_safe_replay_used_write_context", False) or (live_workflow or {}).get("write_context_used", False) or (live_safe_replay or {}).get("write_context_used", False))
    structurally_present = bool(app_context_summary.get("auth_mode", "anonymous") != "anonymous" or auth_families or auth_required)
    not_applied = int(result_counts.get("not_applied", 0))
    applied = int(result_counts.get("applied", 0))
    replay_failure_category = _auth_replay_failure_category(reason_counts, status_counts, error_counts)
    notes = _auth_diagnostic_notes(
        replay_failure_category,
        auth_required=auth_required,
        auth_supplied=auth_supplied,
        write_required=write_required,
        write_supplied=write_supplied,
        structurally_present=structurally_present,
        applied=applied,
        not_applied=not_applied,
    )
    return {
        "schema_version": "auth_diagnostics_summary.v1",
        "auth_mode": app_context_summary.get("auth_mode", "unknown"),
        "auth_scope_hints": app_context_summary.get("auth_scope_hints", []),
        "auth_header_families": auth_families,
        "required_header_family_counts": required_header_counts,
        "approved_auth_context_required": auth_required,
        "approved_auth_context_supplied": auth_supplied,
        "approved_write_context_required": write_required,
        "approved_write_context_supplied": write_supplied,
        "auth_context_gap": bool(auth_required and not auth_supplied),
        "write_context_gap": bool(write_required and not write_supplied),
        "auth_structurally_present": structurally_present,
        "auth_applied_result_counts": result_counts,
        "auth_structurally_present_but_not_applied": bool(structurally_present and not_applied > 0 and applied == 0),
        "workflow_reason_counts": {str(key): int(value) for key, value in reason_counts.items()} if isinstance(reason_counts, dict) else {},
        "failure_class_counts": {str(key): int(value) for key, value in failure_classes.items()} if isinstance(failure_classes, dict) else {},
        "http_status_counts": status_counts,
        "result_error_counts": error_counts,
        "replay_failure_category": replay_failure_category,
        "sanitized_notes": notes,
    }



def build_attack_brief_summary(
    app_context: dict[str, Any] | None,
    app_context_summary: dict[str, Any] | None = None,
    *,
    dryrun_rubric_name: str | None = None,
    dryrun_rubric_rationale: str | None = None,
) -> dict[str, Any]:
    app_context = app_context if isinstance(app_context, dict) else {}
    app_context_summary = app_context_summary if isinstance(app_context_summary, dict) else {}
    tool_schemas = [item for item in app_context.get("tool_action_schema", []) if isinstance(item, dict)]
    boundary = app_context.get("tenant_user_boundary", {}) if isinstance(app_context.get("tenant_user_boundary"), dict) else {}
    boundary_selectors = [item for item in boundary.get("candidate_boundary_selectors", []) if isinstance(item, dict)]
    fields = _field_names(tool_schemas)
    dispatch_fields = _matching_fields(fields, DISPATCH_FIELD_HINTS)
    user_fields = _matching_fields(fields, USER_FIELD_HINTS)
    tenant_fields = _matching_fields(fields, TENANT_FIELD_HINTS)
    resource_fields = _matching_fields(fields, RESOURCE_FIELD_HINTS)
    secret_fields = _matching_fields(fields, SECRET_FIELD_HINTS)
    action_counts = app_context_summary.get("action_class_counts", {}) if isinstance(app_context_summary.get("action_class_counts", {}), dict) else {}
    sensitivity_tags = app_context_summary.get("data_sensitivity_tags", [])
    auth_mode = app_context_summary.get("auth_mode", "unknown")

    probe = _top_probe(dispatch_fields, user_fields, tenant_fields, resource_fields, secret_fields, action_counts)
    risk_themes = _risk_themes(dispatch_fields, user_fields, tenant_fields, resource_fields, secret_fields, action_counts, sensitivity_tags)
    rubric = dryrun_rubric_name or "n/a"
    return {
        "schema_version": "attack_brief_summary.v1",
        "auth_focus": f"mode:{auth_mode}; approved_auth:{bool(app_context_summary.get('requires_approved_auth_context', False))}; approved_write:{bool(app_context_summary.get('requires_approved_write_context', False))}",
        "action_focus": _flat_counts(action_counts),
        "sensitivity_focus": _join(sensitivity_tags),
        "boundary_candidate_fields": _first_n([*user_fields, *tenant_fields, *resource_fields], 12),
        "boundary_candidate_classes": _selector_classes(boundary_selectors),
        "boundary_candidate_locations": _selector_locations(boundary_selectors),
        "boundary_reason_categories": app_context_summary.get("boundary_reason_categories", boundary.get("reason_categories", [])),
        "boundary_selector_count": int(app_context_summary.get("candidate_boundary_selector_count", len(boundary_selectors))),
        "dispatch_candidate_fields": _first_n(dispatch_fields, 8),
        "secret_like_fields": _first_n(secret_fields, 8),
        "risk_themes": risk_themes,
        "top_targeted_probe": probe,
        "targeted_missing_context_questions": targeted_missing_context_questions(risk_themes),
        "dryrun_rubric_name": rubric,
        "dryrun_rubric_rationale": dryrun_rubric_rationale or rubric_rationale(rubric, risk_themes, probe),
    }


def build_rerun_trigger_summary(
    coverage_summary: dict[str, Any],
    auth_diagnostics_summary: dict[str, Any],
    binding_audit_summary: dict[str, Any] | None = None,
    app_context_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return sanitized conditions that should force this evidence path to be rerun."""

    binding_audit_summary = binding_audit_summary if isinstance(binding_audit_summary, dict) else {}
    app_context_summary = app_context_summary if isinstance(app_context_summary, dict) else {}
    gaps = {str(item) for item in coverage_summary.get("coverage_gaps", [])}
    triggers: list[tuple[str, str]] = []

    if app_context_summary.get("operation_count") or app_context_summary.get("tool_action_schema_count") or app_context_summary.get("action_class_counts"):
        triggers.append(("tool_action_schema_or_scope_changes", "rerun when tool/action schemas, operation order, action class, or exposed scope changes"))
    if auth_diagnostics_summary.get("approved_auth_context_required") or auth_diagnostics_summary.get("approved_write_context_required") or auth_diagnostics_summary.get("auth_context_gap") or auth_diagnostics_summary.get("write_context_gap"):
        triggers.append(("auth_or_write_context_changes", "rerun when approved auth, session, target environment, or staging write context changes"))
    if "workflow_blocked" in gaps or "no_live_or_workflow_replay" in gaps or coverage_summary.get("live_workflow_replay_executed"):
        triggers.append(("workflow_execution_or_policy_changes", "rerun when workflow replay policy, host/environment continuity, or executable step status changes"))
    pending = int((binding_audit_summary.get("status_counts", {}) or {}).get("pending", 0) or 0)
    unapplied = int(binding_audit_summary.get("unapplied_binding_count", 0) or 0)
    planned = int(coverage_summary.get("planned_response_binding_count", 0) or 0)
    if planned or pending or unapplied or "bindings_not_fully_applied" in gaps:
        triggers.append(("response_binding_review_or_behavior_changes", "rerun when response bindings are approved, rejected, replaced, newly inferred, or stop applying structurally"))
    boundary_candidates = int(coverage_summary.get("tenant_user_boundary_candidate_count", 0) or 0)
    if boundary_candidates or "tenant_user_boundary_unproven" in gaps:
        triggers.append(("tenant_user_boundary_selector_changes", "rerun when user, tenant, resource, route, or ownership-boundary selectors change"))
    if coverage_summary.get("redthread_dryrun_executed"):
        triggers.append(("redthread_rubric_or_attack_brief_changes", "rerun when the selected RedThread rubric, attack brief, or top targeted probe changes"))

    if not triggers:
        triggers.append(("evidence_envelope_changes", "rerun when the tested input, tool scope, auth posture, binding behavior, or release policy changes"))

    deduped = list(dict.fromkeys(triggers))
    return {
        "schema_version": "rerun_trigger_summary.v1",
        "triggers": [code for code, _ in deduped],
        "explanations": [text for _, text in deduped],
    }



def targeted_missing_context_questions(risk_themes: list[str] | None = None) -> list[str]:
    risk_set = set(risk_themes or [])
    questions: list[str] = []
    if "dispatch_surface" in risk_set:
        questions.append("Is the action/path dispatch allowlisted server-side for this actor?")
    if "tenant_user_boundary" in risk_set:
        questions.append("Can this actor access another actor's object with this identifier class?")
    if "secret_like_fields" in risk_set:
        questions.append("Are secret-like fields server-derived or rejected when supplied by untrusted clients?")
    if "write_surface" in risk_set:
        questions.append("Can this write/destructive operation run only with approved staging context and human review?")
    return questions[:3]


def rubric_rationale(rubric_name: str | None, risk_themes: list[str] | None = None, probe: str | None = None) -> str:
    rubric = str(rubric_name or "n/a")
    risk_themes = risk_themes or []
    if rubric == "prompt_injection":
        return "Selected because chat/message/prompt-like fields or endpoints need prompt-injection probing."
    if rubric == "sensitive_info":
        if "secret_like_fields" in risk_themes:
            return "Selected because secret/token-like or sensitive data fields were detected."
        return "Selected because sensitive-data exposure risk was detected."
    if rubric == "authorization_bypass":
        if "dispatch_surface" in risk_themes:
            return "Selected because generic action/dispatch fields need authorization-boundary probing."
        if "tenant_user_boundary" in risk_themes:
            return "Selected because user/tenant/resource identifiers need ownership-boundary probing."
        return "Selected because the target needs authorization-boundary probing."
    if rubric == "n/a":
        return "No RedThread dry-run rubric was recorded for this run."
    return f"Selected rubric `{rubric}` from bridge-generated RedThread campaign metadata."


def _decision_explanation(category: str) -> str:
    explanations = {
        "approved_clean_evidence": "No blockers or review warnings were present in the tested evidence envelope.",
        "manual_review_required_for_write_paths": "Write-capable paths are present, so the safe outcome is human review rather than silent approval.",
        "redthread_replay_failed": "RedThread replay failed; this is a release blocker for the tested evidence envelope.",
        "auth_or_context_blocked": "Required approved auth or write context was missing or mismatched, so this is not a confirmed security finding.",
        "auth_or_replay_failed": "Live replay failed because auth/session/environment/replay did not succeed; this is not a confirmed security finding by itself.",
        "binding_or_workflow_context_blocked": "Workflow state or response-binding evidence was incomplete or mismatched.",
        "sandbox_only_blocked": "Sandbox-only items block release unless explicitly waived.",
        "blocked_without_confirmed_finding": "The run blocked, but no confirmed security finding category was emitted.",
        "insufficient_decision_detail": "The run did not emit enough structured detail to classify the decision precisely.",
    }
    return explanations.get(category, "Decision category is not yet classified.")


def _auth_applied_result_counts(live_workflow: dict[str, Any] | None, live_safe_replay: dict[str, Any] | None) -> dict[str, int]:
    counts = {"applied": 0, "not_applied": 0}
    for result in _executed_results(live_workflow, live_safe_replay):
        if result.get("auth_applied"):
            counts["applied"] += 1
        else:
            counts["not_applied"] += 1
    return {key: value for key, value in counts.items() if value > 0}



def _http_status_counts(live_workflow: dict[str, Any] | None, live_safe_replay: dict[str, Any] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in _executed_results(live_workflow, live_safe_replay):
        status = result.get("status_code")
        if status is None:
            continue
        key = f"http_status_{int(status)}"
        counts[key] = counts.get(key, 0) + 1
    return counts



def _result_error_counts(live_workflow: dict[str, Any] | None, live_safe_replay: dict[str, Any] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in _executed_results(live_workflow, live_safe_replay):
        error = _sanitized_result_error(result)
        if not error:
            continue
        counts[error] = counts.get(error, 0) + 1
    return counts



def _executed_results(live_workflow: dict[str, Any] | None, live_safe_replay: dict[str, Any] | None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if isinstance(live_safe_replay, dict):
        results.extend(item for item in live_safe_replay.get("results", []) if isinstance(item, dict))
    if isinstance(live_workflow, dict):
        for workflow_result in live_workflow.get("results", []):
            if isinstance(workflow_result, dict):
                results.extend(item for item in workflow_result.get("results", []) if isinstance(item, dict))
    return results



def _sanitized_result_error(result: dict[str, Any]) -> str:
    error = str(result.get("error", "")).strip()
    if not error:
        return ""
    if error.startswith("url_error"):
        return "url_error"
    if error in {"http_error", "timeout", "case_not_executable"}:
        return error
    return "runtime_error"



def _auth_replay_failure_category(reason_counts: dict[str, Any], status_counts: dict[str, int], error_counts: dict[str, int]) -> str:
    reason_keys = {str(key) for key in reason_counts}
    if "missing_auth_context" in reason_keys:
        return "missing_auth_context"
    if "missing_write_context" in reason_keys:
        return "missing_write_context"
    if "auth_header_family_mismatch" in reason_keys:
        return "auth_header_family_mismatch"
    if reason_keys & {"host_continuity_mismatch", "target_env_mismatch"}:
        return "environment_or_continuity_mismatch"
    if status_counts.get("http_status_401") or status_counts.get("http_status_403") or reason_keys & {"http_status_401", "http_status_403"}:
        return "server_rejected_auth"
    if _has_failure_http_status(set(status_counts) | reason_keys) or error_counts:
        return "runtime_replay_failure"
    if not reason_keys:
        return "none"
    return "workflow_context_blocked"


def _has_failure_http_status(status_keys: set[str]) -> bool:
    for key in status_keys:
        if not key.startswith("http_status_"):
            continue
        try:
            status = int(key.removeprefix("http_status_"))
        except ValueError:
            return True
        if status >= 400:
            return True
    return False


def _auth_diagnostic_notes(
    replay_failure_category: str,
    *,
    auth_required: bool,
    auth_supplied: bool,
    write_required: bool,
    write_supplied: bool,
    structurally_present: bool,
    applied: int,
    not_applied: int,
) -> list[str]:
    notes: list[str] = []
    if auth_required and not auth_supplied:
        notes.append("Approved auth context was required but not supplied.")
    if write_required and not write_supplied:
        notes.append("Approved write context was required but not supplied.")
    if structurally_present and not_applied > 0 and applied == 0:
        notes.append("Auth was structurally expected, but no executed replay result recorded auth application.")
    if replay_failure_category == "server_rejected_auth":
        notes.append("Replay reached the server but received an auth-like rejection status.")
    elif replay_failure_category == "environment_or_continuity_mismatch":
        notes.append("Replay was blocked by host or target-environment continuity checks.")
    elif replay_failure_category == "auth_header_family_mismatch":
        notes.append("Approved auth context did not satisfy the required auth header family contract.")
    return notes[:4]



def _reason_counts(summary: dict[str, Any], live_workflow: dict[str, Any] | None) -> dict[str, int]:
    source = (live_workflow or {}).get("reason_counts") or summary.get("live_workflow_reason_counts", {}) or {}
    return {str(key): int(value) for key, value in source.items()} if isinstance(source, dict) else {}


def _live_safe_failure_present(live_safe_replay: dict[str, Any] | None) -> bool:
    if not isinstance(live_safe_replay, dict):
        return False
    executed = int(live_safe_replay.get("executed_case_count", 0))
    success = int(live_safe_replay.get("success_count", 0))
    return executed > success


def _first_reason(reason_keys: set[str], candidates: set[str]) -> str:
    for reason in sorted(candidates):
        if reason in reason_keys:
            return reason
    return sorted(reason_keys)[0] if reason_keys else "unknown"


def _first_http_or(default: str, reason_keys: set[str]) -> str:
    for reason in sorted(reason_keys):
        if reason.startswith("http_status_"):
            return reason
    return default


def _value_from(summary: dict[str, Any], workflow: dict[str, Any] | None, summary_key: str, workflow_key: str, default: Any) -> Any:
    if summary_key in summary:
        return summary[summary_key]
    if workflow and workflow_key in workflow:
        return workflow[workflow_key]
    return default


def _fixture_fields(fixture: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for key in ("query_params", "body_fields", "response_fields"):
        values = fixture.get(key, [])
        if isinstance(values, list):
            fields.extend(str(value).strip().lower() for value in values if str(value).strip())
    fields.extend(
        str(fixture.get(key, "")).strip().lower()
        for key in ("path", "endpoint_family", "workflow_group")
        if str(fixture.get(key, "")).strip()
    )
    return sorted(dict.fromkeys(fields))


def _fixture_action_class(fixture: dict[str, Any]) -> str:
    method = str(fixture.get("method", "GET")).upper()
    attack_types = {str(value) for value in fixture.get("candidate_attack_types", [])}
    replay_class = str(fixture.get("replay_class", ""))
    if method in {"DELETE", "PATCH"} or "destructive_action_abuse" in attack_types:
        return "destructive"
    if method in {"POST", "PUT"} or replay_class in {"manual_review", "sandbox_only"}:
        return "write"
    return "read"


def _fixture_sensitivity_tags(fixture: dict[str, Any], fields: list[str], secret_fields: list[str], message_fields: list[str]) -> list[str]:
    tags: list[str] = []
    sensitivity = str(fixture.get("data_sensitivity", "")).lower()
    if sensitivity == "secret" or secret_fields:
        tags.append("secret_like")
    if sensitivity == "pii" or _matching_fields(fields, USER_FIELD_HINTS | {"email", "phone", "name"}):
        tags.append("user_data")
    if message_fields:
        tags.append("support_message_like")
    return sorted(dict.fromkeys(tags))


def _selector_classes(selectors: list[dict[str, Any]]) -> list[str]:
    return sorted(dict.fromkeys(str(selector.get("class")) for selector in selectors if selector.get("class")))


def _selector_locations(selectors: list[dict[str, Any]]) -> list[str]:
    return sorted(dict.fromkeys(str(selector.get("location")) for selector in selectors if selector.get("location")))


def _field_names(tool_schemas: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for schema in tool_schemas:
        for key in ("request_fields", "response_fields"):
            values = schema.get(key, [])
            if isinstance(values, list):
                fields.extend(str(value) for value in values)
    return sorted(dict.fromkeys(field for field in fields if field))


def _matching_fields(fields: list[str], hints: set[str]) -> list[str]:
    return [field for field in fields if _has_hint(field, hints)]


def _has_hint(value: str, hints: set[str]) -> bool:
    lowered = value.lower()
    parts = set(lowered.replace("-", "_").replace(".", "_").split("_"))
    return any(hint in lowered or hint in parts for hint in hints)


def _top_probe(dispatch_fields: list[str], user_fields: list[str], tenant_fields: list[str], resource_fields: list[str], secret_fields: list[str], action_counts: dict[str, Any]) -> str:
    if dispatch_fields:
        return "Verify action/dispatch fields are server-side allowlisted for this actor."
    if user_fields or tenant_fields:
        return "Verify user/tenant identifiers are server-side derived or ownership-checked, not trusted from the client."
    if resource_fields:
        return "Verify this actor cannot access another actor's resource identifier class."
    if secret_fields:
        return "Verify secret-like fields are not accepted from untrusted clients or exposed in responses."
    if int(action_counts.get("write", 0)) or int(action_counts.get("destructive", 0)):
        return "Replay write/destructive operations only with approved staging context and human review."
    return "No high-value targeted probe was inferred from sanitized structural metadata."


def _risk_themes(dispatch_fields: list[str], user_fields: list[str], tenant_fields: list[str], resource_fields: list[str], secret_fields: list[str], action_counts: dict[str, Any], sensitivity_tags: Any) -> list[str]:
    themes: list[str] = []
    if dispatch_fields:
        themes.append("dispatch_surface")
    if user_fields or tenant_fields or resource_fields:
        themes.append("tenant_user_boundary")
    if secret_fields or "secret_like" in set(sensitivity_tags or []):
        themes.append("secret_like_fields")
    if int(action_counts.get("write", 0)) or int(action_counts.get("destructive", 0)):
        themes.append("write_surface")
    if sensitivity_tags:
        themes.append("sensitive_data")
    return sorted(dict.fromkeys(themes)) or ["no_specific_theme"]


def _first_n(items: list[str], limit: int) -> list[str]:
    return sorted(dict.fromkeys(items))[:limit]


def _flat_counts(payload: dict[str, Any]) -> str:
    if not payload:
        return "none"
    return ",".join(f"{key}:{payload[key]}" for key in sorted(payload))


def _join(items: Any) -> str:
    if not items:
        return "none"
    return ",".join(str(item) for item in items)

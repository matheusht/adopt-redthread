from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.bridge.evidence_summaries import build_attack_brief_summary, build_auth_diagnostics_summary, build_coverage_summary, build_decision_reason_summary, build_rerun_trigger_summary

def build_evidence_report(run_dir: str | Path, output_path: str | Path | None = None) -> str:
    root = Path(run_dir)
    summary = _load(root / "workflow_summary.json")
    gate = _load(root / "gate_verdict.json")
    workflow = _load_optional(root / "live_workflow_replay.json")
    live_safe = _load_optional(root / "live_safe_replay.json")
    redthread = _load_optional(root / "redthread_replay_verdict.json")
    runtime_inputs = _load_optional(root / "redthread_runtime_inputs.json") or {}

    requirement_summary = summary.get("live_workflow_requirement_summary", {})
    binding_summary = summary.get("live_workflow_binding_application_summary", {})
    workflow_status = _workflow_status(workflow)
    redthread_passed = redthread.get("passed") if redthread else summary.get("redthread_replay_passed")
    blocker_detail = _blocker_detail(gate, summary, workflow)
    app_context_summary = summary.get("app_context_summary", {}) or runtime_inputs.get("app_context_summary", {})
    decision_reason_summary = summary.get("decision_reason_summary") or build_decision_reason_summary(
        gate,
        summary,
        live_workflow=workflow,
        live_safe_replay=live_safe,
        redthread=redthread,
    )
    coverage_summary = summary.get("coverage_summary") or build_coverage_summary(
        summary,
        live_workflow=workflow,
        live_safe_replay=live_safe,
        app_context_summary=app_context_summary,
    )
    attack_brief_summary = summary.get("attack_brief_summary") or runtime_inputs.get("attack_brief_summary") or build_attack_brief_summary(
        runtime_inputs.get("app_context", {}),
        app_context_summary,
        dryrun_rubric_name=summary.get("dryrun_rubric_name"),
        dryrun_rubric_rationale=summary.get("dryrun_rubric_rationale"),
    )
    auth_diagnostics_summary = summary.get("auth_diagnostics_summary") or build_auth_diagnostics_summary(
        summary,
        live_workflow=workflow,
        live_safe_replay=live_safe,
        app_context_summary=app_context_summary,
    )
    binding_audit_summary = summary.get("live_workflow_binding_audit_summary") or (workflow or {}).get("binding_audit_summary", {})
    not_proven_lines = _not_proven_lines(coverage_summary, auth_diagnostics_summary)
    reviewer_action = _reviewer_action(gate, summary, decision_reason_summary, coverage_summary)
    trusted_evidence = _trusted_evidence_line(summary, workflow_status, requirement_summary, binding_summary, redthread_passed)
    finding_type = _finding_type_line(decision_reason_summary, auth_diagnostics_summary)
    next_evidence_lines = _next_evidence_lines(coverage_summary, auth_diagnostics_summary, binding_audit_summary, attack_brief_summary)
    rerun_trigger_summary = build_rerun_trigger_summary(
        coverage_summary,
        auth_diagnostics_summary,
        binding_audit_summary,
        app_context_summary,
    )
    rerun_trigger_lines = _rerun_trigger_lines(rerun_trigger_summary)

    lines = [
        f"# Evidence Report: {root.name}",
        "",
        "## Reviewer quick read",
        "",
        "This section is the no-walkthrough summary: what was tested, what evidence ran, why the gate decided, and what is still not proven.",
        "",
        f"- Tested input: `{Path(str(summary.get('input_file', 'unknown'))).name}` via `{summary.get('ingestion', 'unknown')}` with `{summary.get('fixture_count', 0)}` fixtures.",
        f"- Workflow exercised: {_workflow_quick_read(summary, workflow_status, requirement_summary, binding_summary)}",
        f"- RedThread evaluated: replay_passed=`{bool(redthread_passed)}`, dry_run_executed=`{summary.get('redthread_dryrun_executed', False)}`, rubric=`{summary.get('dryrun_rubric_name', 'n/a')}`.",
        f"- Local gate outcome: `{gate.get('decision', summary.get('gate_decision', 'unknown'))}`; category=`{decision_reason_summary.get('category', 'unknown')}`; confirmed_security_finding=`{decision_reason_summary.get('confirmed_security_finding', False)}`.",
        f"- Reviewer action: {reviewer_action}",
        f"- Why this outcome: {decision_reason_summary.get('explanation', 'n/a')}",
        f"- Still not proven: {_reviewer_gap_line(coverage_summary)}",
        f"- Next useful probe: {attack_brief_summary.get('top_targeted_probe', 'n/a')}",
        "",
        "## Silent reviewer checklist",
        "",
        "Use this section to answer the validation questions without opening raw artifacts.",
        "",
        f"- Ship, change, or block? {reviewer_action}",
        f"- What evidence should I trust most? {trusted_evidence}",
        f"- What is still unclear or weak? {_reviewer_gap_line(coverage_summary)}",
        f"- Which next probe would increase confidence? {attack_brief_summary.get('top_targeted_probe', 'n/a')}",
        f"- What evidence should I collect next? {_inline_next_evidence(next_evidence_lines)}",
        f"- What changes force a rerun? {_inline_rerun_triggers(rerun_trigger_lines)}",
        f"- Confirmed issue, auth/replay failure, or insufficient evidence? {finding_type}",
        "- Repeat before release? Rerun this evidence path when tool scopes, auth/write context, binding behavior, or boundary selectors change before release.",
        "",
        "## Decision",
        "",
        "RedThread replay/dry-run is evidence for this report; the final `approve` / `review` / `block` verdict below is currently emitted by the local Adopt RedThread bridge gate.",
        "",
        f"- Local bridge gate decision: `{gate.get('decision', summary.get('gate_decision', 'unknown'))}`",
        f"- Local gate warnings: `{_join(gate.get('warnings', []))}`",
        f"- Local gate blockers: `{_join(gate.get('blockers', []))}`",
        f"- Exact decision reason (local bridge gate): {blocker_detail}",
        f"- Decision reason category: `{decision_reason_summary.get('category', 'unknown')}`",
        f"- Confirmed security finding: `{decision_reason_summary.get('confirmed_security_finding', False)}`",
        f"- Reviewer action: {reviewer_action}",
        f"- Decision reason explanation: {decision_reason_summary.get('explanation', 'n/a')}",
        "",
        "## Input",
        "",
        f"- Ingestion: `{summary.get('ingestion', 'unknown')}`",
        f"- Input artifact: `{Path(str(summary.get('input_file', 'unknown'))).name}`",
        f"- Fixture count: `{summary.get('fixture_count', 0)}`",
        "",
        "## Coverage confidence",
        "",
        f"- Coverage label: `{coverage_summary.get('label', 'unknown')}`",
        f"- Live safe replay executed: `{coverage_summary.get('live_safe_replay_executed', False)}`",
        f"- Live workflow replay executed: `{coverage_summary.get('live_workflow_replay_executed', False)}`",
        f"- Successful workflows: `{coverage_summary.get('successful_workflow_count', 0)}`",
        f"- Blocked workflows: `{coverage_summary.get('blocked_workflow_count', 0)}`",
        f"- Applied/planned bindings: `{coverage_summary.get('applied_response_binding_count', 0)}/{coverage_summary.get('planned_response_binding_count', 0)}`",
        f"- Tenant/user boundary probed: `{coverage_summary.get('tenant_user_boundary_probed', False)}`",
        f"- Coverage gaps: `{_join(coverage_summary.get('coverage_gaps', []))}`",
        "",
        "## Auth delivery diagnostics",
        "",
        f"- Auth mode: `{auth_diagnostics_summary.get('auth_mode', 'unknown')}`",
        f"- Auth header families: `{_join(auth_diagnostics_summary.get('auth_header_families', []))}`",
        f"- Required header family counts: `{_flat_counts(auth_diagnostics_summary.get('required_header_family_counts', {}))}`",
        f"- Approved auth context required/supplied: `{auth_diagnostics_summary.get('approved_auth_context_required', False)}/{auth_diagnostics_summary.get('approved_auth_context_supplied', False)}`",
        f"- Approved write context required/supplied: `{auth_diagnostics_summary.get('approved_write_context_required', False)}/{auth_diagnostics_summary.get('approved_write_context_supplied', False)}`",
        f"- Auth applied result counts: `{_flat_counts(auth_diagnostics_summary.get('auth_applied_result_counts', {}))}`",
        f"- HTTP status counts: `{_flat_counts(auth_diagnostics_summary.get('http_status_counts', {}))}`",
        f"- Replay/auth failure category: `{auth_diagnostics_summary.get('replay_failure_category', 'unknown')}`",
        f"- Auth diagnostic notes: `{_join(auth_diagnostics_summary.get('sanitized_notes', []))}`",
        "",
        "## App context for RedThread",
        "",
        f"- Context schema: `{app_context_summary.get('schema_version', 'n/a')}`",
        f"- Operations described: `{app_context_summary.get('operation_count', 0)}`",
        f"- Tool/action schemas described: `{app_context_summary.get('tool_action_schema_count', 0)}`",
        f"- Action classes: `{_flat_counts(app_context_summary.get('action_class_counts', {}))}`",
        f"- Auth mode observed from structural hints: `{app_context_summary.get('auth_mode', 'unknown')}`",
        f"- Auth scope hints: `{_join(app_context_summary.get('auth_scope_hints', []))}`",
        f"- Approved auth context required: `{app_context_summary.get('requires_approved_auth_context', False)}`",
        f"- Approved write context required: `{app_context_summary.get('requires_approved_write_context', False)}`",
        f"- Approved context required, any kind: `{app_context_summary.get('requires_approved_context', False)}`",
        f"- Sensitivity tags: `{_join(app_context_summary.get('data_sensitivity_tags', []))}`",
        f"- Candidate user fields: `{app_context_summary.get('candidate_user_field_count', 0)}`",
        f"- Candidate tenant fields: `{app_context_summary.get('candidate_tenant_field_count', 0)}`",
        f"- Candidate resource fields: `{app_context_summary.get('candidate_resource_field_count', 0)}`",
        f"- Candidate route params: `{app_context_summary.get('candidate_route_param_count', 0)}`",
        f"- Boundary selectors: `{app_context_summary.get('candidate_boundary_selector_count', 0)}`",
        f"- Boundary reason categories: `{_join(app_context_summary.get('boundary_reason_categories', []))}`",
        "",
        "## Attack brief for RedThread",
        "",
        f"- Risk themes: `{_join(attack_brief_summary.get('risk_themes', []))}`",
        f"- Top targeted probe/question: {attack_brief_summary.get('top_targeted_probe', 'n/a')}",
        f"- Targeted missing-context questions: `{_join(attack_brief_summary.get('targeted_missing_context_questions', []))}`",
        f"- Boundary candidate fields: `{_join(attack_brief_summary.get('boundary_candidate_fields', []))}`",
        f"- Boundary candidate classes: `{_join(attack_brief_summary.get('boundary_candidate_classes', []))}`",
        f"- Boundary candidate locations: `{_join(attack_brief_summary.get('boundary_candidate_locations', []))}`",
        f"- Dispatch candidate fields: `{_join(attack_brief_summary.get('dispatch_candidate_fields', []))}`",
        f"- Secret-like fields: `{_join(attack_brief_summary.get('secret_like_fields', []))}`",
        f"- Dry-run rubric rationale: {attack_brief_summary.get('dryrun_rubric_rationale', 'n/a')}",
        "",
        "## Workflow evidence",
        "",
        f"- Live workflow replay executed: `{summary.get('live_workflow_replay_executed', False)}`",
        f"- Workflow count: `{summary.get('live_workflow_count', 0)}`",
        f"- Successful workflows: `{workflow_status['successful']}`",
        f"- Blocked workflows: `{workflow_status['blocked']}`",
        f"- Aborted workflows: `{workflow_status['aborted']}`",
        f"- Workflow classes: `{_flat_counts(requirement_summary.get('workflow_class_counts', {}))}`",
        f"- Failure classes: `{_flat_counts(summary.get('live_workflow_failure_class_summary', {}))}`",
        "",
        "## Binding evidence",
        "",
        f"- Declared response bindings: `{requirement_summary.get('declared_response_binding_count', binding_summary.get('planned_response_binding_count', 0))}`",
        f"- Applied response bindings: `{requirement_summary.get('applied_response_binding_count', binding_summary.get('applied_response_binding_count', 0))}`",
        f"- Unapplied response bindings: `{binding_summary.get('unapplied_response_binding_count', 0)}`",
        f"- Binding failures: `{_flat_counts(binding_summary.get('binding_application_failure_counts', {}))}`",
        f"- Binding audit schema: `{binding_audit_summary.get('schema_version', 'n/a')}`",
        f"- Binding audit statuses: `{_flat_counts(binding_audit_summary.get('status_counts', {}))}`",
        f"- Binding origins: `{_flat_counts(binding_audit_summary.get('origin_counts', {}))}`",
        f"- Binding target classes: `{_flat_counts(binding_audit_summary.get('target_field_counts', {}))}`",
        f"- Bindings that changed later requests structurally: `{binding_audit_summary.get('changed_later_request_count', 0)}`",
        f"- Binding audit records: `{_binding_audit_records(binding_audit_summary.get('audit_records', []))}`",
        "",
        "## RedThread evidence",
        "",
        "This section records what RedThread consumed or returned. It is not, by itself, the final local bridge gate decision.",
        "",
        f"- RedThread replay passed: `{bool(redthread_passed)}`",
        f"- RedThread dry-run executed: `{summary.get('redthread_dryrun_executed', False)}`",
        f"- Dry-run case: `{summary.get('dryrun_case_id', 'n/a')}`",
        f"- Dry-run rubric: `{summary.get('dryrun_rubric_name', 'n/a')}`",
        f"- Dry-run rubric rationale: {attack_brief_summary.get('dryrun_rubric_rationale', 'n/a')}",
        "",
        "## Why this decision is correct",
        "",
        _decision_narrative(gate, summary),
        "",
        "## Next evidence to collect",
        "",
        *next_evidence_lines,
        "",
        "## Rerun triggers",
        "",
        *rerun_trigger_lines,
        "",
        "## Not proven by this run",
        "",
        *not_proven_lines,
        "",
    ]
    report = "\n".join(lines)
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
    return report


def _workflow_quick_read(
    summary: dict[str, Any],
    workflow_status: dict[str, int],
    requirement_summary: dict[str, Any],
    binding_summary: dict[str, Any],
) -> str:
    if not summary.get("live_workflow_replay_executed", False):
        return "No live workflow replay executed; evidence is fixture/replay/dry-run only."
    classes = _flat_counts(requirement_summary.get("workflow_class_counts", {}))
    applied = requirement_summary.get("applied_response_binding_count", binding_summary.get("applied_response_binding_count", 0))
    planned = requirement_summary.get("declared_response_binding_count", binding_summary.get("planned_response_binding_count", 0))
    return (
        f"Live workflow replay executed with `{workflow_status['successful']}` successful, "
        f"`{workflow_status['blocked']}` blocked, and `{workflow_status['aborted']}` aborted workflows; "
        f"classes=`{classes}`; bindings_applied_planned=`{applied}/{planned}`."
    )



def _reviewer_gap_line(coverage_summary: dict[str, Any]) -> str:
    gaps = coverage_summary.get("coverage_gaps", [])
    if not gaps:
        return "No explicit coverage gaps were emitted for this evidence envelope."
    return _join(gaps)



def _trusted_evidence_line(
    summary: dict[str, Any],
    workflow_status: dict[str, int],
    requirement_summary: dict[str, Any],
    binding_summary: dict[str, Any],
    redthread_passed: Any,
) -> str:
    parts: list[str] = []
    if summary.get("live_workflow_replay_executed", False):
        parts.append(
            "live workflow replay status successful:{successful},blocked:{blocked},aborted:{aborted}".format(
                successful=workflow_status["successful"],
                blocked=workflow_status["blocked"],
                aborted=workflow_status["aborted"],
            )
        )
    planned = requirement_summary.get("declared_response_binding_count", binding_summary.get("planned_response_binding_count", 0))
    applied = requirement_summary.get("applied_response_binding_count", binding_summary.get("applied_response_binding_count", 0))
    if planned:
        parts.append(f"response bindings applied:{applied}/{planned}")
    if redthread_passed is not None:
        parts.append(f"RedThread replay passed:{bool(redthread_passed)}")
    if summary.get("redthread_dryrun_executed", False):
        parts.append(f"RedThread dry-run rubric:{summary.get('dryrun_rubric_name', 'n/a')}")
    if not parts:
        return "fixture normalization only; no live workflow, binding, or RedThread replay evidence was available"
    return "; ".join(parts)



def _inline_next_evidence(lines: list[str]) -> str:
    cleaned = [line[2:] if line.startswith("- ") else line for line in lines]
    return " | ".join(cleaned[:3]) if cleaned else "No additional evidence request emitted."



def _inline_rerun_triggers(lines: list[str]) -> str:
    cleaned = [line[2:] if line.startswith("- ") else line for line in lines]
    return " | ".join(cleaned[:3]) if cleaned else "No rerun trigger emitted."



def _rerun_trigger_lines(rerun_trigger_summary: dict[str, Any]) -> list[str]:
    explanations = [str(item) for item in rerun_trigger_summary.get("explanations", []) if str(item).strip()]
    if not explanations:
        return ["- rerun when the tested evidence envelope changes"]
    return [f"- {item}" for item in explanations]



def _next_evidence_lines(
    coverage_summary: dict[str, Any],
    auth_diagnostics_summary: dict[str, Any],
    binding_audit_summary: dict[str, Any],
    attack_brief_summary: dict[str, Any],
) -> list[str]:
    gaps = {str(item) for item in coverage_summary.get("coverage_gaps", [])}
    replay_failure = str(auth_diagnostics_summary.get("replay_failure_category", "unknown"))
    lines: list[str] = []
    if auth_diagnostics_summary.get("write_context_gap") or replay_failure == "missing_write_context":
        lines.append("- supply approved non-production staging write context and rerun workflow replay; keep write paths at review until human approval")
    if auth_diagnostics_summary.get("auth_context_gap") or replay_failure in {"missing_auth_context", "auth_header_family_mismatch", "server_rejected_auth"}:
        lines.append("- supply or refresh approved auth context matching the observed structural auth families, then rerun replay")
    if "workflow_blocked" in gaps:
        lines.append("- resolve the emitted workflow blocker category and rerun live workflow replay under the existing safety policy")
    unapplied = int(binding_audit_summary.get("unapplied_binding_count", 0) or 0)
    pending = int((binding_audit_summary.get("status_counts", {}) or {}).get("pending", 0) or 0)
    if "bindings_not_fully_applied" in gaps or unapplied or pending:
        lines.append("- review, approve, reject, or replace pending response bindings, then rerun to confirm structural request continuity")
    if "tenant_user_boundary_unproven" in gaps:
        probe = attack_brief_summary.get("top_targeted_probe", "run the top targeted ownership-boundary probe")
        lines.append(f"- run the targeted ownership-boundary probe: {probe}")
    if "no_live_or_workflow_replay" in gaps:
        lines.append("- add a bounded safe-read or approved workflow replay; current evidence is fixture/replay/dry-run only")
    if not lines:
        lines.append("- no additional evidence request was emitted by this run; rerun before release if tool scopes, auth, write behavior, bindings, or boundary selectors change")
    return list(dict.fromkeys(lines))



def _finding_type_line(decision_reason_summary: dict[str, Any], auth_diagnostics_summary: dict[str, Any]) -> str:
    category = str(decision_reason_summary.get("category", "unknown"))
    if decision_reason_summary.get("confirmed_security_finding", False):
        return f"confirmed security finding; decision category:{category}"
    replay_failure = str(auth_diagnostics_summary.get("replay_failure_category", "unknown"))
    if category == "auth_or_context_blocked" or replay_failure not in {"none", "unknown", "None", ""}:
        return f"auth/replay/context failure:{replay_failure}; not a confirmed vulnerability"
    if category in {"insufficient_coverage", "tenant_boundary_unproven", "binding_review_needed"}:
        return f"insufficient or unproven evidence:{category}; not a confirmed vulnerability"
    return f"not confirmed as a security finding; decision category:{category}"



def _reviewer_action(
    gate: dict[str, Any],
    summary: dict[str, Any],
    decision_reason_summary: dict[str, Any],
    coverage_summary: dict[str, Any],
) -> str:
    decision = str(gate.get("decision", summary.get("gate_decision", "unknown")))
    category = str(decision_reason_summary.get("category", "unknown"))
    label = str(coverage_summary.get("label", "unknown"))
    gaps = _join(coverage_summary.get("coverage_gaps", []))
    if decision == "approve":
        return f"ship candidate: local gate approved; coverage:{label}; gaps:{gaps}"
    if decision == "review":
        return f"change/review before ship: {category}; coverage:{label}; gaps:{gaps}"
    if decision == "block" and category == "auth_or_context_blocked":
        primary = decision_reason_summary.get("primary_reason", "required_context_missing")
        return f"block until approved context/replay gap is resolved: {primary}; coverage:{label}; gaps:{gaps}"
    if decision == "block":
        return f"block release: {category}; coverage:{label}; gaps:{gaps}"
    return f"manual triage required: {category}; coverage:{label}; gaps:{gaps}"



def _not_proven_lines(coverage_summary: dict[str, Any], auth_diagnostics_summary: dict[str, Any]) -> list[str]:
    gaps = {str(item) for item in coverage_summary.get("coverage_gaps", [])}
    lines: list[str] = []
    if "no_live_or_workflow_replay" in gaps:
        lines.append("- live app behavior or workflow continuity; this run is fixture/replay/dry-run only")
    if "workflow_blocked" in gaps:
        lines.append("- successful execution of the blocked workflow under approved context")
    if "bindings_not_fully_applied" in gaps:
        lines.append("- complete response-binding application for every planned binding")
    if "tenant_user_boundary_unproven" in gaps:
        lines.append("- cross-user, cross-tenant, or resource-ownership enforcement")
    if "auth_or_replay_blocked" in gaps or auth_diagnostics_summary.get("replay_failure_category") not in {None, "none", "unknown"}:
        lines.append("- valid auth/session/write-context delivery for this run; this is not proof of a confirmed vulnerability")
    lines.extend(
        [
            "- production publish gating wired into a real release system",
            "- stable behavior of any external live app forever",
            "- RedThread independently owning live workflow execution for Adopt-managed sessions",
            "- broad authenticated/write-path coverage beyond this evidence envelope",
        ]
    )
    deduped = list(dict.fromkeys(lines))
    return deduped



def _decision_narrative(gate: dict[str, Any], summary: dict[str, Any]) -> str:
    decision = str(gate.get("decision", summary.get("gate_decision", "unknown")))
    warnings = gate.get("warnings", [])
    if decision == "approve":
        return "The workflow evidence and RedThread evidence passed with no blockers or review warnings."
    if decision == "review" and "manual_review_required_for_write_paths" in warnings:
        return "The workflow succeeded and RedThread replay passed, but write paths are present. The correct safe outcome is human review, not silent approval."
    if decision == "block":
        return _blocker_detail(gate, summary, None)
    return "The local bridge gate emitted this decision from combined bridge replay evidence and RedThread evidence."


def _blocker_detail(gate: dict[str, Any], summary: dict[str, Any], workflow: dict[str, Any] | None) -> str:
    decision = str(gate.get("decision", summary.get("gate_decision", "unknown")))
    blockers = [str(item) for item in gate.get("blockers", [])]
    if decision == "approve":
        return "approve: no blockers or review warnings were present."
    if decision == "review":
        return f"review: {_join(gate.get('warnings', []))}."
    if "live_workflow_blocked_steps_present" in blockers:
        reason_counts = _reason_counts(summary, workflow)
        reasons = _flat_counts(reason_counts)
        plain_reasons = _plain_reason_counts(reason_counts)
        return f"block: live workflow had blocked steps ({reasons}). {plain_reasons}"
    if blockers:
        return f"block: {_join(blockers)}."
    return f"{decision}: no more specific gate reason was emitted."


def _reason_counts(summary: dict[str, Any], workflow: dict[str, Any] | None) -> dict[str, Any]:
    if workflow and isinstance(workflow.get("reason_counts"), dict):
        return workflow.get("reason_counts", {})
    value = summary.get("live_workflow_reason_counts", {})
    return value if isinstance(value, dict) else {}


def _plain_reason_counts(reason_counts: dict[str, Any]) -> str:
    explanations = {
        "missing_write_context": "Approved staging write context was required but was not supplied, so no write step was executed.",
        "missing_auth_context": "Approved auth context was required but was not supplied.",
        "binding_review_required": "A response binding required review before execution.",
        "step_not_executable": "At least one workflow step was not executable under the current policy.",
        "host_continuity_mismatch": "The workflow crossed hosts where same-host continuity was required.",
        "target_env_mismatch": "The workflow crossed target environments where same-environment continuity was required.",
        "response_binding_missing": "A required response binding value was missing.",
        "response_binding_target_missing": "A required response binding target was missing.",
    }
    details = [explanations[key] for key in sorted(reason_counts) if key in explanations]
    return " ".join(details) if details else "Inspect live_workflow_replay.json for the exact blocking reason."


def _workflow_status(workflow: dict[str, Any] | None) -> dict[str, int]:
    if not workflow:
        return {"successful": 0, "blocked": 0, "aborted": 0}
    return {
        "successful": int(workflow.get("successful_workflow_count", 0)),
        "blocked": int(workflow.get("blocked_workflow_count", 0)),
        "aborted": int(workflow.get("aborted_workflow_count", 0)),
    }


def _flat_counts(payload: dict[str, Any]) -> str:
    if not payload:
        return "none"
    return ",".join(f"{key}:{payload[key]}" for key in sorted(payload))


def _join(items: list[Any]) -> str:
    return "none" if not items else ",".join(str(item) for item in items)


def _binding_audit_records(records: list[dict[str, Any]]) -> str:
    if not records:
        return "none"
    parts = []
    for record in records[:5]:
        parts.append(
            "{binding_id}:{origin}/{review_status}->applied:{applied};target:{target};reason:{reason}".format(
                binding_id=record.get("binding_id", "unknown"),
                origin=record.get("origin", "unknown"),
                review_status=record.get("review_status", "unknown"),
                applied=record.get("applied_at_runtime", False),
                target=record.get("target_field", "unknown"),
                reason=record.get("allow_or_hold_reason", "unknown"),
            )
        )
    return ";".join(parts)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _load_optional(path: Path) -> dict[str, Any] | None:
    return _load(path) if path.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a markdown evidence report from a bridge run directory.")
    parser.add_argument("--run-dir", default="runs/reviewed_write_reference", help="Run directory containing workflow_summary.json")
    parser.add_argument("--output", default=None, help="Output markdown path; defaults to <run-dir>/evidence_report.md")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    output = Path(args.output) if args.output else run_dir / "evidence_report.md"
    report = build_evidence_report(run_dir, output)
    print(f"evidence report -> {output}")
    print(report)


if __name__ == "__main__":
    main()

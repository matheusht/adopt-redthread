from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.bridge.evidence_summaries import build_attack_brief_summary, build_coverage_summary, build_decision_reason_summary

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

    lines = [
        f"# Evidence Report: {root.name}",
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
        f"- Candidate route params: `{app_context_summary.get('candidate_route_param_count', 0)}`",
        "",
        "## Attack brief for RedThread",
        "",
        f"- Risk themes: `{_join(attack_brief_summary.get('risk_themes', []))}`",
        f"- Top targeted probe/question: {attack_brief_summary.get('top_targeted_probe', 'n/a')}",
        f"- Targeted missing-context questions: `{_join(attack_brief_summary.get('targeted_missing_context_questions', []))}`",
        f"- Boundary candidate fields: `{_join(attack_brief_summary.get('boundary_candidate_fields', []))}`",
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
        "## Not proven by this run",
        "",
        "- production publish gating wired into a real release system",
        "- stable behavior of any external live app forever",
        "- RedThread independently owning live workflow execution for Adopt-managed sessions",
        "- broad authenticated/write-path coverage beyond this reviewed reference path",
        "",
    ]
    report = "\n".join(lines)
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
    return report


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

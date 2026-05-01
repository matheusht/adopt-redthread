from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.bridge.evidence_summaries import build_attack_brief_summary, build_auth_diagnostics_summary, build_coverage_summary

DEFAULT_RUN_DIR = REPO_ROOT / "runs" / "reviewed_write_reference"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "boundary_probe_plan"
SCHEMA_VERSION = "adopt_redthread.boundary_probe_plan.v1"

SENSITIVE_MARKERS = (
    "value_preview",
    "set-cookie",
    "authorization:",
    "cookie:",
    "bearer ",
    "acct-123",
)


def build_boundary_probe_plan(
    run_dir: str | Path = DEFAULT_RUN_DIR,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Build a sanitized tenant/user boundary probe plan from existing run evidence.

    The plan is intentionally not an executor. It turns existing app-context and
    coverage evidence into a reviewer-readable next-probe contract without copying
    raw request values, response values, credentials, bodies, or session material.
    """

    root = Path(run_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    summary = _load_optional(root / "workflow_summary.json")
    runtime_inputs = _load_optional(root / "redthread_runtime_inputs.json")
    live_workflow = _load_optional(root / "live_workflow_replay.json")
    live_safe = _load_optional(root / "live_safe_replay.json")

    app_context = runtime_inputs.get("app_context", {}) if isinstance(runtime_inputs, dict) else {}
    app_context_summary = summary.get("app_context_summary") or runtime_inputs.get("app_context_summary", {})
    boundary = app_context.get("tenant_user_boundary", {}) if isinstance(app_context.get("tenant_user_boundary"), dict) else {}
    selectors = [item for item in boundary.get("candidate_boundary_selectors", []) if isinstance(item, dict)]
    coverage = summary.get("coverage_summary") or build_coverage_summary(
        summary,
        live_workflow=live_workflow,
        live_safe_replay=live_safe,
        app_context_summary=app_context_summary,
    )
    attack_brief = summary.get("attack_brief_summary") or runtime_inputs.get("attack_brief_summary") or build_attack_brief_summary(
        app_context,
        app_context_summary,
        dryrun_rubric_name=summary.get("dryrun_rubric_name"),
        dryrun_rubric_rationale=summary.get("dryrun_rubric_rationale"),
    )
    auth_diagnostics = summary.get("auth_diagnostics_summary") or build_auth_diagnostics_summary(
        summary,
        live_workflow=live_workflow,
        live_safe_replay=live_safe,
        app_context_summary=app_context_summary,
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_run": _display_path(root),
        "artifact_policy": "Boundary probe plan contains structural selector classes, locations, operation IDs, and path templates only. It is not an executor and must not contain raw HAR/session/cookie/header/body/request/response values.",
        "boundary_probe_status": _probe_status(coverage, selectors),
        "candidate_summary": _candidate_summary(app_context_summary, selectors),
        "probe_objective": attack_brief.get("top_targeted_probe", "Verify that cross-actor resource access is denied for boundary-relevant selector classes."),
        "safety_policy": _safety_policy(auth_diagnostics),
        "probe_plan": _probe_plan(selectors, auth_diagnostics),
        "expected_evidence": _expected_evidence(),
        "decision_policy": {
            "no_verdict_change_from_plan_alone": True,
            "review_remains_review_until_probe_evidence_exists": True,
            "confirmed_finding_requires_observed_policy_violation": True,
            "auth_or_context_failure_is_not_a_confirmed_vulnerability": True,
        },
        "source_coverage": {
            "coverage_label": coverage.get("label", "unknown"),
            "coverage_gaps": coverage.get("coverage_gaps", []),
            "tenant_user_boundary_probed": bool(coverage.get("tenant_user_boundary_probed", False)),
            "tenant_user_boundary_candidate_count": int(coverage.get("tenant_user_boundary_candidate_count", 0) or 0),
        },
    }
    marker_audit = _marker_audit(json.dumps(payload, sort_keys=True))
    payload["configured_sensitive_marker_check"] = marker_audit
    if fail_on_marker_hit and marker_audit["marker_hit_count"]:
        raise RuntimeError(f"boundary probe plan marker audit failed with {marker_audit['marker_hit_count']} hits")

    markdown = _markdown(payload)
    markdown_audit = _marker_audit(markdown)
    if fail_on_marker_hit and markdown_audit["marker_hit_count"]:
        raise RuntimeError(f"boundary probe plan markdown marker audit failed with {markdown_audit['marker_hit_count']} hits")
    payload["configured_sensitive_marker_check"] = markdown_audit

    (output_root / "tenant_user_boundary_probe_plan.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output_root / "tenant_user_boundary_probe_plan.md").write_text(markdown, encoding="utf-8")
    return payload


def _candidate_summary(app_context_summary: dict[str, Any], selectors: list[dict[str, Any]]) -> dict[str, Any]:
    class_counts: dict[str, int] = {}
    location_counts: dict[str, int] = {}
    operations: set[str] = set()
    path_templates: set[str] = set()
    selector_records: list[dict[str, Any]] = []
    for selector in selectors:
        boundary_class = str(selector.get("class", "unknown"))
        location = str(selector.get("location", "unknown"))
        class_counts[boundary_class] = class_counts.get(boundary_class, 0) + 1
        location_counts[location] = location_counts.get(location, 0) + 1
        if selector.get("operation_id"):
            operations.add(str(selector["operation_id"]))
        if selector.get("path_template"):
            path_templates.add(str(selector["path_template"]))
        selector_records.append({
            "name": str(selector.get("name", "unknown")),
            "class": boundary_class,
            "location": location,
            "operation_id": str(selector.get("operation_id", "unknown")),
            "path_template": str(selector.get("path_template", "unknown")),
            "reason_category": str(selector.get("reason_category", "unknown")),
        })
    return {
        "candidate_user_field_count": int(app_context_summary.get("candidate_user_field_count", 0) or 0),
        "candidate_tenant_field_count": int(app_context_summary.get("candidate_tenant_field_count", 0) or 0),
        "candidate_resource_field_count": int(app_context_summary.get("candidate_resource_field_count", 0) or 0),
        "candidate_route_param_count": int(app_context_summary.get("candidate_route_param_count", 0) or 0),
        "candidate_boundary_selector_count": len(selectors),
        "selector_class_counts": class_counts,
        "selector_location_counts": location_counts,
        "reason_categories": sorted({str(item) for item in app_context_summary.get("boundary_reason_categories", []) if str(item)}),
        "operation_ids": sorted(operations),
        "path_templates": sorted(path_templates),
        "selectors": selector_records[:20],
    }


def _probe_status(coverage: dict[str, Any], selectors: list[dict[str, Any]]) -> str:
    gaps = {str(item) for item in coverage.get("coverage_gaps", [])}
    if bool(coverage.get("tenant_user_boundary_probed", False)) and "tenant_user_boundary_unproven" not in gaps:
        return "already_probed_in_source_evidence"
    if selectors or int(coverage.get("tenant_user_boundary_candidate_count", 0) or 0):
        return "needs_boundary_probe"
    return "no_boundary_candidates_detected"


def _safety_policy(auth_diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_only_not_execution": True,
        "production_writes_forbidden": True,
        "raw_values_forbidden": True,
        "requires_approved_non_production_target": True,
        "requires_approved_auth_context": bool(auth_diagnostics.get("approved_auth_context_required", False)),
        "requires_approved_write_context": bool(auth_diagnostics.get("approved_write_context_required", False)),
        "allowed_execution_modes": [
            "local deterministic evidence generation",
            "policy-allowed safe read replay",
            "reviewed non-production staging workflow with explicit approved context",
        ],
    }


def _probe_plan(selectors: list[dict[str, Any]], auth_diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    target_selectors = selectors[:3]
    selector_text = ", ".join(
        f"{item.get('class', 'unknown')} selector `{item.get('name', 'unknown')}` at `{item.get('location', 'unknown')}`"
        for item in target_selectors
    ) or "the highest-risk user, tenant, resource, or route selector class"
    return [
        {
            "step": 1,
            "name": "choose_approved_test_context",
            "instruction": "Use only an approved non-production target with two distinct test actors or tenants. Do not paste actor, tenant, resource, credential, or body values into evidence artifacts.",
        },
        {
            "step": 2,
            "name": "select_boundary_selector_class",
            "instruction": f"Start with {selector_text}; keep only selector names, classes, locations, operation IDs, and path templates in artifacts.",
        },
        {
            "step": 3,
            "name": "establish_actor_owned_control",
            "instruction": "Confirm the workflow succeeds for the actor's own resource or tenant scope under the existing safe-read or reviewed-staging policy.",
        },
        {
            "step": 4,
            "name": "attempt_cross_actor_boundary_probe",
            "instruction": "Repeat the same structural operation with a different actor or tenant selector class supplied through approved test context, expecting denial or no data exposure.",
        },
        {
            "step": 5,
            "name": "record_sanitized_result",
            "instruction": "Record only allow/deny outcome class, status family, replay/auth failure category, gate decision, and whether the boundary probe passed, failed, or was blocked by missing context.",
        },
    ]


def _expected_evidence() -> dict[str, Any]:
    return {
        "pass_condition": "Own-resource control succeeds and cross-actor or cross-tenant probe is denied without exposing another actor's data.",
        "review_condition": "Probe cannot run because approved non-production context, auth context, write context, or safe selector mapping is missing.",
        "block_condition": "Cross-actor or cross-tenant probe succeeds where denial was expected, or required replay/auth evidence fails closed.",
        "sanitized_fields_to_record": [
            "boundary_probe_executed",
            "selector_class",
            "selector_location",
            "operation_id",
            "path_template",
            "own_scope_result_class",
            "cross_scope_result_class",
            "http_status_family",
            "replay_failure_category",
            "gate_decision",
        ],
    }


def _load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _marker_audit(text: str) -> dict[str, Any]:
    lowered = text.casefold()
    hits = [marker for marker in SENSITIVE_MARKERS if marker.casefold() in lowered]
    return {
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(SENSITIVE_MARKERS),
        "marker_hit_count": len(hits),
        "passed": len(hits) == 0,
        "markers": sorted(set(hits)),
    }


def _markdown(payload: dict[str, Any]) -> str:
    candidates = payload["candidate_summary"]
    safety = payload["safety_policy"]
    coverage = payload["source_coverage"]
    lines = [
        "# Tenant/User Boundary Probe Plan",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Source run: `{payload['source_run']}`",
        f"- Boundary probe status: `{payload['boundary_probe_status']}`",
        f"- Probe objective: {payload['probe_objective']}",
        f"- Source coverage label: `{coverage['coverage_label']}`",
        f"- Source coverage gaps: `{_join(coverage['coverage_gaps'])}`",
        f"- Boundary already probed: `{coverage['tenant_user_boundary_probed']}`",
        "",
        "## Candidate selector summary",
        "",
        f"- Boundary selectors: `{candidates['candidate_boundary_selector_count']}`",
        f"- User fields: `{candidates['candidate_user_field_count']}`",
        f"- Tenant fields: `{candidates['candidate_tenant_field_count']}`",
        f"- Resource fields: `{candidates['candidate_resource_field_count']}`",
        f"- Route params: `{candidates['candidate_route_param_count']}`",
        f"- Selector classes: `{_flat_counts(candidates['selector_class_counts'])}`",
        f"- Selector locations: `{_flat_counts(candidates['selector_location_counts'])}`",
        f"- Reason categories: `{_join(candidates['reason_categories'])}`",
        f"- Operation IDs: `{_join(candidates['operation_ids'])}`",
        f"- Path templates: `{_join(candidates['path_templates'])}`",
        "",
        "## Sanitized selector records",
        "",
        "| Name | Class | Location | Operation | Path template | Reason |",
        "|---|---|---|---|---|---|",
    ]
    for selector in candidates["selectors"]:
        lines.append(
            f"| `{selector['name']}` | `{selector['class']}` | `{selector['location']}` | `{selector['operation_id']}` | `{selector['path_template']}` | `{selector['reason_category']}` |"
        )
    if not candidates["selectors"]:
        lines.append("| `none_detected` | `n/a` | `n/a` | `n/a` | `n/a` | `n/a` |")
    lines.extend([
        "",
        "## Safety policy",
        "",
        f"- Plan only, not execution: `{safety['plan_only_not_execution']}`",
        f"- Production writes forbidden: `{safety['production_writes_forbidden']}`",
        f"- Raw values forbidden: `{safety['raw_values_forbidden']}`",
        f"- Requires approved non-production target: `{safety['requires_approved_non_production_target']}`",
        f"- Requires approved auth context: `{safety['requires_approved_auth_context']}`",
        f"- Requires approved write context: `{safety['requires_approved_write_context']}`",
        f"- Allowed execution modes: `{_join(safety['allowed_execution_modes'])}`",
        "",
        "## Probe steps",
        "",
    ])
    for step in payload["probe_plan"]:
        lines.append(f"{step['step']}. **{step['name']}** — {step['instruction']}")
    expected = payload["expected_evidence"]
    decision = payload["decision_policy"]
    audit = payload["configured_sensitive_marker_check"]
    lines.extend([
        "",
        "## Expected evidence interpretation",
        "",
        f"- Pass condition: {expected['pass_condition']}",
        f"- Review condition: {expected['review_condition']}",
        f"- Block condition: {expected['block_condition']}",
        f"- Sanitized fields to record: `{_join(expected['sanitized_fields_to_record'])}`",
        "",
        "## Decision policy",
        "",
        f"- Plan alone changes verdict: `{not decision['no_verdict_change_from_plan_alone']}`",
        f"- Review remains review until probe evidence exists: `{decision['review_remains_review_until_probe_evidence_exists']}`",
        f"- Confirmed finding requires observed policy violation: `{decision['confirmed_finding_requires_observed_policy_violation']}`",
        f"- Auth/context failure is not a confirmed vulnerability: `{decision['auth_or_context_failure_is_not_a_confirmed_vulnerability']}`",
        "",
        "## Configured sensitive marker check",
        "",
        f"- Passed: `{audit['passed']}`",
        f"- Marker hits: `{audit['marker_hit_count']}`",
        f"- Marker set: `{audit['marker_set']}` (`{audit['marker_count']}` configured strings)",
        "",
    ])
    return "\n".join(lines)


def _flat_counts(counts: dict[str, Any]) -> str:
    if not isinstance(counts, dict) or not counts:
        return "none"
    return ",".join(f"{key}:{counts[key]}" for key in sorted(counts))


def _join(values: Any) -> str:
    if not values:
        return "none"
    if isinstance(values, (list, tuple, set)):
        return ",".join(str(item) for item in values) if values else "none"
    return str(values)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized tenant/user boundary probe plan from existing evidence.")
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if configured sensitive markers are present (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write artifacts even when configured sensitive markers are present")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()

    plan = build_boundary_probe_plan(args.run_dir, output_dir=args.output_dir, fail_on_marker_hit=args.fail_on_marker_hit)
    print(f"tenant/user boundary probe plan -> {Path(args.output_dir) / 'tenant_user_boundary_probe_plan.md'}")
    print(json.dumps({
        "boundary_probe_status": plan["boundary_probe_status"],
        "selector_count": plan["candidate_summary"]["candidate_boundary_selector_count"],
        "marker_hits": plan["configured_sensitive_marker_check"]["marker_hit_count"],
        "marker_audit_passed": plan["configured_sensitive_marker_check"]["passed"],
    }, indent=2))


if __name__ == "__main__":
    main()

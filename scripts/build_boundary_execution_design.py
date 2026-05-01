from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_boundary_probe_plan import DEFAULT_OUTPUT_DIR as DEFAULT_PLAN_DIR
from scripts.build_boundary_probe_plan import SENSITIVE_MARKERS

DEFAULT_PLAN = DEFAULT_PLAN_DIR / "tenant_user_boundary_probe_plan.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "boundary_execution_design"
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "tenant-user-boundary-execution-design.md"
SCHEMA_VERSION = "adopt_redthread.boundary_execution_design.v1"

RESULT_STATUSES = (
    "not_run",
    "passed_boundary_probe",
    "failed_boundary_probe",
    "blocked_missing_context",
    "auth_or_replay_failed",
)


def build_boundary_execution_design(
    *,
    probe_plan: str | Path = DEFAULT_PLAN,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    doc_path: str | Path = DEFAULT_DOC_PATH,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Write the tenant/user boundary execution design and sanitized result contract.

    This is intentionally a design artifact, not an executor. It defines the
    approved-context and result shapes needed before implementation can safely run
    own-scope vs cross-scope boundary probes.
    """

    plan_path = Path(probe_plan)
    plan = _load_optional(plan_path)
    candidate_summary = plan.get("candidate_summary", {}) if isinstance(plan.get("candidate_summary"), dict) else {}
    selectors = [item for item in candidate_summary.get("selectors", []) if isinstance(item, dict)]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_probe_plan": _display_path(plan_path),
        "design_status": "executor_not_implemented",
        "implementation_gate": "do_not_execute_until_approved_non_production_context_exists",
        "artifact_policy": "This design may contain selector names, classes, locations, operation IDs, path templates, outcome classes, and status families. It must not contain raw actor IDs, tenant IDs, resource IDs, session material, credential values, request/response bodies, or write-context values.",
        "selector_scope": _selector_scope(candidate_summary, selectors),
        "approved_context_contract": _approved_context_contract(),
        "execution_flow": _execution_flow(selectors),
        "result_contract": _result_contract(),
        "decision_mapping": _decision_mapping(),
        "privacy_and_safety_invariants": _privacy_and_safety_invariants(),
        "blocked_until": _blocked_until(),
    }
    markdown = _markdown(payload)
    audit = _marker_audit(json.dumps(payload, sort_keys=True) + "\n" + markdown)
    payload["configured_sensitive_marker_check"] = audit
    if fail_on_marker_hit and audit["marker_hit_count"]:
        raise RuntimeError(f"boundary execution design marker audit failed with {audit['marker_hit_count']} hits")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "tenant_user_boundary_execution_design.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output_root / "tenant_user_boundary_execution_design.md").write_text(markdown, encoding="utf-8")
    doc = Path(doc_path)
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(markdown, encoding="utf-8")
    return payload


def _selector_scope(candidate_summary: dict[str, Any], selectors: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_boundary_selector_count": int(candidate_summary.get("candidate_boundary_selector_count", len(selectors)) or 0),
        "selector_class_counts": candidate_summary.get("selector_class_counts", {}) if isinstance(candidate_summary.get("selector_class_counts", {}), dict) else {},
        "selector_location_counts": candidate_summary.get("selector_location_counts", {}) if isinstance(candidate_summary.get("selector_location_counts", {}), dict) else {},
        "reason_categories": candidate_summary.get("reason_categories", []) if isinstance(candidate_summary.get("reason_categories", []), list) else [],
        "operation_ids": candidate_summary.get("operation_ids", []) if isinstance(candidate_summary.get("operation_ids", []), list) else [],
        "path_templates": candidate_summary.get("path_templates", []) if isinstance(candidate_summary.get("path_templates", []), list) else [],
        "example_selectors": selectors[:5],
    }


def _approved_context_contract() -> dict[str, Any]:
    return {
        "schema_version": "adopt_redthread.boundary_probe_context.v1",
        "storage_policy": "local_ignored_file_only_never_checked_in",
        "required_top_level_fields": [
            "schema_version",
            "target_environment",
            "execution_mode",
            "actor_scopes",
            "selector_bindings",
            "operator_approval",
        ],
        "target_environment": {
            "required_fields": ["environment_label", "base_url_label", "production", "approved_for_boundary_probe"],
            "rules": [
                "production must be false",
                "approved_for_boundary_probe must be true",
                "base_url_label must be a label, not a raw URL containing credentials or query values",
            ],
        },
        "execution_mode": {
            "allowed_values": ["safe_read_replay", "reviewed_non_production_workflow"],
            "write_rule": "write-capable paths require the existing approved write-context gate and remain review until evidence is captured",
        },
        "actor_scopes": {
            "required_labels": ["own_scope", "cross_scope"],
            "value_rule": "store raw actor, tenant, auth, and resource values only in the local approved context; generated evidence may reference labels only",
        },
        "selector_bindings": {
            "required_fields": ["selector_name", "selector_class", "selector_location", "operation_id", "path_template", "own_scope_value_ref", "cross_scope_value_ref"],
            "value_ref_rule": "value_ref points to approved local context entries; generated artifacts never copy resolved values",
        },
        "operator_approval": {
            "required_fields": ["approved_by", "approved_at", "scope_note"],
            "rule": "approval records why this non-production target and both actor scopes are safe to probe",
        },
    }


def _execution_flow(selectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary = selectors[0] if selectors else {}
    selector_hint = {
        "selector_name": primary.get("name", "highest_risk_boundary_selector"),
        "selector_class": primary.get("class", "unknown"),
        "selector_location": primary.get("location", "unknown"),
        "operation_id": primary.get("operation_id", "unknown"),
        "path_template": primary.get("path_template", "unknown"),
    }
    return [
        {
            "step": 1,
            "name": "load_approved_context",
            "records": ["context_schema_version", "target_environment_label", "execution_mode"],
            "blocks_on": ["missing_context", "production_target", "unapproved_target", "missing_actor_scopes"],
        },
        {
            "step": 2,
            "name": "select_boundary_case",
            "selector_hint": selector_hint,
            "records": ["selector_name", "selector_class", "selector_location", "operation_id", "path_template"],
            "blocks_on": ["missing_selector_binding", "unsafe_selector_mapping"],
        },
        {
            "step": 3,
            "name": "run_own_scope_control",
            "purpose": "prove the workflow can access the actor's own resource or tenant scope before cross-scope interpretation",
            "records": ["own_scope_result_class", "own_scope_status_family", "own_scope_replay_failure_category"],
            "blocks_on": ["auth_or_replay_failed", "own_scope_control_failed"],
        },
        {
            "step": 4,
            "name": "run_cross_scope_probe",
            "purpose": "attempt the same structural operation against a different actor or tenant selector reference and expect denial or no data exposure",
            "records": ["cross_scope_result_class", "cross_scope_status_family", "cross_scope_replay_failure_category"],
            "blocks_on": ["auth_or_replay_failed"],
        },
        {
            "step": 5,
            "name": "write_sanitized_result",
            "records": ["result_status", "gate_decision", "confirmed_security_finding", "sanitized_notes"],
            "blocks_on": ["configured_sensitive_marker_hit"],
        },
    ]


def _result_contract() -> dict[str, Any]:
    return {
        "schema_version": "adopt_redthread.boundary_probe_result.v1",
        "allowed_statuses": list(RESULT_STATUSES),
        "required_fields": [
            "schema_version",
            "result_status",
            "boundary_probe_executed",
            "selector_evidence",
            "own_scope_result_class",
            "cross_scope_result_class",
            "http_status_family",
            "replay_failure_category",
            "gate_decision",
            "confirmed_security_finding",
            "configured_sensitive_marker_check",
        ],
        "selector_evidence_fields": ["selector_name", "selector_class", "selector_location", "operation_id", "path_template"],
        "allowed_result_classes": ["allowed", "denied", "no_data_exposed", "blocked", "not_run", "unknown"],
        "allowed_http_status_family_examples": ["2xx", "3xx", "4xx", "5xx", "not_applicable", "unknown"],
        "raw_value_fields_forbidden": [
            "actor_id",
            "tenant_id",
            "resource_id",
            "credential_value",
            "session_value",
            "request_body",
            "response_body",
        ],
    }


def _decision_mapping() -> dict[str, Any]:
    return {
        "passed_boundary_probe": {
            "meaning": "own-scope control worked and cross-scope probe was denied or exposed no data",
            "gate_effect": "may remove tenant_user_boundary_unproven from the evidence gaps, but does not automatically approve write-capable paths",
            "confirmed_security_finding": False,
        },
        "failed_boundary_probe": {
            "meaning": "cross-scope probe was allowed where denial/no-exposure was expected",
            "gate_effect": "block until fixed or disproven with stronger approved evidence",
            "confirmed_security_finding": True,
        },
        "blocked_missing_context": {
            "meaning": "approved target, actor scope, selector binding, auth context, or write context was missing",
            "gate_effect": "review; missing context is not a confirmed vulnerability",
            "confirmed_security_finding": False,
        },
        "auth_or_replay_failed": {
            "meaning": "the probe could not be interpreted because auth, replay, host, environment, or policy continuity failed",
            "gate_effect": "review or block depending on existing gate policy; not a confirmed vulnerability by itself",
            "confirmed_security_finding": False,
        },
        "not_run": {
            "meaning": "no boundary execution evidence exists",
            "gate_effect": "keep tenant_user_boundary_unproven wording",
            "confirmed_security_finding": False,
        },
    }


def _privacy_and_safety_invariants() -> list[str]:
    return [
        "Generated artifacts never include raw actor, tenant, resource, credential, session, request-body, or response-body values.",
        "Production targets are rejected before execution.",
        "Write-capable paths require the existing approved non-production write-context gate.",
        "Own-scope control must run before cross-scope results are interpreted.",
        "Auth/replay/context failures are not labeled as confirmed security findings.",
        "The local bridge owns approve/review/block until RedThread has a validated generic enforcement contract.",
    ]


def _blocked_until() -> list[str]:
    return [
        "external human cold-review validation confirms reviewers understand current evidence and gaps",
        "approved non-production target with two safe actor scopes is supplied",
        "approved context uses value references rather than generated-artifact raw values",
        "boundary result artifact parser and marker audit exist",
        "report/matrix wording is updated to consume boundary result evidence without changing verdict semantics",
    ]


def _markdown(payload: dict[str, Any]) -> str:
    selector_scope = payload["selector_scope"]
    context = payload["approved_context_contract"]
    result = payload["result_contract"]
    mapping = payload["decision_mapping"]
    lines = [
        "# Tenant/User Boundary Execution Design",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Design status: `{payload['design_status']}`",
        f"- Implementation gate: `{payload['implementation_gate']}`",
        f"- Source probe plan: `{payload['source_probe_plan']}`",
        "- This is not an executor and is not release validation by itself.",
        "",
        "## Selector scope from current evidence",
        "",
        f"- Boundary selectors: `{selector_scope['candidate_boundary_selector_count']}`",
        f"- Selector classes: `{_flat_counts(selector_scope['selector_class_counts'])}`",
        f"- Selector locations: `{_flat_counts(selector_scope['selector_location_counts'])}`",
        f"- Reason categories: `{_join(selector_scope['reason_categories'])}`",
        f"- Operation IDs: `{_join(selector_scope['operation_ids'])}`",
        f"- Path templates: `{_join(selector_scope['path_templates'])}`",
        "",
        "## Approved context contract",
        "",
        f"- Schema: `{context['schema_version']}`",
        f"- Storage policy: `{context['storage_policy']}`",
        f"- Required top-level fields: `{_join(context['required_top_level_fields'])}`",
        f"- Target environment required fields: `{_join(context['target_environment']['required_fields'])}`",
        f"- Target rules: `{_join(context['target_environment']['rules'])}`",
        f"- Execution modes: `{_join(context['execution_mode']['allowed_values'])}`",
        f"- Write rule: {context['execution_mode']['write_rule']}",
        f"- Actor scope labels: `{_join(context['actor_scopes']['required_labels'])}`",
        f"- Actor value rule: {context['actor_scopes']['value_rule']}",
        f"- Selector binding fields: `{_join(context['selector_bindings']['required_fields'])}`",
        f"- Selector value-ref rule: {context['selector_bindings']['value_ref_rule']}",
        f"- Operator approval fields: `{_join(context['operator_approval']['required_fields'])}`",
        "",
        "## Execution flow to implement later",
        "",
    ]
    for step in payload["execution_flow"]:
        lines.append(f"{step['step']}. **{step['name']}**")
        if step.get("purpose"):
            lines.append(f"   - Purpose: {step['purpose']}")
        if step.get("selector_hint"):
            lines.append(f"   - Selector hint: `{json.dumps(step['selector_hint'], sort_keys=True)}`")
        lines.append(f"   - Records: `{_join(step['records'])}`")
        lines.append(f"   - Blocks on: `{_join(step['blocks_on'])}`")
    lines.extend([
        "",
        "## Boundary result contract",
        "",
        f"- Schema: `{result['schema_version']}`",
        f"- Allowed statuses: `{_join(result['allowed_statuses'])}`",
        f"- Required fields: `{_join(result['required_fields'])}`",
        f"- Selector evidence fields: `{_join(result['selector_evidence_fields'])}`",
        f"- Allowed result classes: `{_join(result['allowed_result_classes'])}`",
        f"- HTTP status family examples: `{_join(result['allowed_http_status_family_examples'])}`",
        f"- Raw-value fields forbidden: `{_join(result['raw_value_fields_forbidden'])}`",
        "",
        "## Decision mapping",
        "",
    ])
    for status in RESULT_STATUSES:
        item = mapping[status]
        lines.extend([
            f"### `{status}`",
            "",
            f"- Meaning: {item['meaning']}",
            f"- Gate effect: {item['gate_effect']}",
            f"- Confirmed security finding: `{item['confirmed_security_finding']}`",
            "",
        ])
    lines.extend([
        "## Privacy and safety invariants",
        "",
    ])
    lines.extend(f"- {item}" for item in payload["privacy_and_safety_invariants"])
    lines.extend([
        "",
        "## Blocked until",
        "",
    ])
    lines.extend(f"- {item}" for item in payload["blocked_until"])
    lines.append("")
    return "\n".join(lines)


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


def _flat_counts(counts: dict[str, Any]) -> str:
    if not counts:
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
    parser = argparse.ArgumentParser(description="Write the tenant/user boundary execution design and result contract.")
    parser.add_argument("--probe-plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--doc-path", default=str(DEFAULT_DOC_PATH))
    parser.add_argument("--fail-on-marker-hit", action="store_true", help="Exit non-zero if configured sensitive markers are present")
    args = parser.parse_args()

    payload = build_boundary_execution_design(
        probe_plan=args.probe_plan,
        output_dir=args.output_dir,
        doc_path=args.doc_path,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"tenant/user boundary execution design -> {Path(args.doc_path)}")
    print(json.dumps({
        "design_status": payload["design_status"],
        "result_schema": payload["result_contract"]["schema_version"],
        "allowed_statuses": payload["result_contract"]["allowed_statuses"],
        "marker_hits": payload["configured_sensitive_marker_check"]["marker_hit_count"],
    }, indent=2))


if __name__ == "__main__":
    main()

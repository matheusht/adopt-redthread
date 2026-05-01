from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_boundary_execution_design import DEFAULT_OUTPUT_DIR as DEFAULT_DESIGN_DIR
from scripts.build_boundary_execution_design import RESULT_STATUSES
from scripts.build_boundary_probe_plan import DEFAULT_OUTPUT_DIR as DEFAULT_PLAN_DIR
from scripts.build_boundary_probe_plan import SENSITIVE_MARKERS

DEFAULT_PROBE_PLAN = DEFAULT_PLAN_DIR / "tenant_user_boundary_probe_plan.json"
DEFAULT_EXECUTION_DESIGN = DEFAULT_DESIGN_DIR / "tenant_user_boundary_execution_design.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "boundary_probe_result"
SCHEMA_VERSION = "adopt_redthread.boundary_probe_result.v1"

ALLOWED_RESULT_CLASSES = {"allowed", "denied", "no_data_exposed", "blocked", "not_run", "unknown"}
ALLOWED_HTTP_STATUS_FAMILIES = {"2xx", "3xx", "4xx", "5xx", "not_applicable", "unknown"}
FORBIDDEN_RAW_FIELD_KEYS = {
    "actor_id",
    "tenant_id",
    "resource_id",
    "credential_value",
    "session_value",
    "request_body",
    "response_body",
    "auth_header",
    "authorization",
    "cookie",
    "set_cookie",
    "raw_value",
    "value_preview",
}


def build_boundary_probe_result(
    *,
    probe_plan: str | Path = DEFAULT_PROBE_PLAN,
    execution_design: str | Path = DEFAULT_EXECUTION_DESIGN,
    observed_result: str | Path | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Write a sanitized tenant/user boundary result artifact.

    This is a result-template/validator, not an executor. With no observed result
    input it writes the current honest state: boundary execution is blocked because
    approved non-production boundary context has not been supplied. If a future
    executor or operator supplies a sanitized observed-result JSON, this function
    validates and normalizes it without copying raw actor, tenant, resource,
    session, credential, request-body, or response-body values.
    """

    plan_path = Path(probe_plan)
    design_path = Path(execution_design)
    plan = _load_optional(plan_path)
    design = _load_optional(design_path)
    observed = _load_optional(Path(observed_result)) if observed_result else None
    if observed:
        observed_audit = _marker_audit(json.dumps(observed, sort_keys=True))
        if fail_on_marker_hit and not observed_audit["passed"]:
            raise RuntimeError(
                "boundary probe observed-result audit failed "
                f"with markers={observed_audit['marker_hit_count']} raw_fields={observed_audit['raw_field_hit_count']}"
            )

    payload = _normalize_observed_result(observed, plan, design) if observed else _blocked_missing_context_result(plan, design)
    payload["schema_version"] = SCHEMA_VERSION
    payload["source_probe_plan"] = _display_path(plan_path)
    payload["source_execution_design"] = _display_path(design_path)
    payload["artifact_policy"] = (
        "Boundary result artifacts contain only selector labels, outcome classes, status families, gate interpretation, "
        "and bounded context-readiness labels. They must not contain raw actor IDs, tenant IDs, resource IDs, session "
        "material, credential values, request bodies, response bodies, or write-context values."
    )
    payload["no_executor_in_this_artifact"] = True
    payload["verdict_semantics_changed"] = False
    payload["configured_sensitive_marker_check"] = _marker_audit(json.dumps(payload, sort_keys=True))
    _validate_contract(payload)
    if fail_on_marker_hit and not payload["configured_sensitive_marker_check"]["passed"]:
        audit = payload["configured_sensitive_marker_check"]
        raise RuntimeError(
            "boundary probe result marker/raw-field audit failed "
            f"with markers={audit['marker_hit_count']} raw_fields={audit['raw_field_hit_count']}"
        )

    markdown = _markdown(payload)
    markdown_audit = _marker_audit(markdown)
    if fail_on_marker_hit and not markdown_audit["passed"]:
        raise RuntimeError(
            "boundary probe result markdown audit failed "
            f"with markers={markdown_audit['marker_hit_count']} raw_fields={markdown_audit['raw_field_hit_count']}"
        )
    payload["configured_sensitive_marker_check"] = markdown_audit

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "tenant_user_boundary_probe_result.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output_root / "tenant_user_boundary_probe_result.md").write_text(markdown, encoding="utf-8")
    return payload


def _blocked_missing_context_result(plan: dict[str, Any], design: dict[str, Any]) -> dict[str, Any]:
    selector = _select_selector(plan, design)
    return {
        "result_status": "blocked_missing_context",
        "boundary_probe_executed": False,
        "selector_evidence": selector,
        "own_scope_result_class": "not_run",
        "cross_scope_result_class": "not_run",
        "http_status_family": "not_applicable",
        "replay_failure_category": "missing_approved_boundary_probe_context",
        "gate_decision": "review",
        "confirmed_security_finding": False,
        "context_readiness": _context_readiness(design),
        "interpretation": _interpretation("blocked_missing_context"),
        "sanitized_notes": [
            "No boundary executor was run by this artifact.",
            "Approved non-production target, actor scopes, selector bindings, and operator approval are required before execution.",
            "Missing boundary context is review evidence, not a confirmed vulnerability.",
        ],
    }


def _normalize_observed_result(observed: dict[str, Any], plan: dict[str, Any], design: dict[str, Any]) -> dict[str, Any]:
    status = str(observed.get("result_status", "not_run"))
    selector = observed.get("selector_evidence") if isinstance(observed.get("selector_evidence"), dict) else _select_selector(plan, design)
    payload = {
        "result_status": status,
        "boundary_probe_executed": bool(observed.get("boundary_probe_executed", status in {"passed_boundary_probe", "failed_boundary_probe", "auth_or_replay_failed"})),
        "selector_evidence": _selector_evidence(selector),
        "own_scope_result_class": str(observed.get("own_scope_result_class", "unknown")),
        "cross_scope_result_class": str(observed.get("cross_scope_result_class", "unknown")),
        "http_status_family": str(observed.get("http_status_family", "unknown")),
        "replay_failure_category": str(observed.get("replay_failure_category", "none")),
        "gate_decision": str(observed.get("gate_decision", _gate_decision_for_status(status))),
        "confirmed_security_finding": bool(observed.get("confirmed_security_finding", status == "failed_boundary_probe")),
        "context_readiness": observed.get("context_readiness") if isinstance(observed.get("context_readiness"), dict) else _context_readiness(design),
        "interpretation": _interpretation(status),
        "sanitized_notes": [str(item) for item in observed.get("sanitized_notes", []) if str(item).strip()][:10],
    }
    if not payload["sanitized_notes"]:
        payload["sanitized_notes"] = ["Sanitized observed result was normalized without raw context values."]
    return payload


def _select_selector(plan: dict[str, Any], design: dict[str, Any]) -> dict[str, str]:
    candidates = []
    candidate_summary = plan.get("candidate_summary", {}) if isinstance(plan.get("candidate_summary"), dict) else {}
    if isinstance(candidate_summary.get("selectors"), list):
        candidates.extend(item for item in candidate_summary["selectors"] if isinstance(item, dict))
    selector_scope = design.get("selector_scope", {}) if isinstance(design.get("selector_scope"), dict) else {}
    if isinstance(selector_scope.get("example_selectors"), list):
        candidates.extend(item for item in selector_scope["example_selectors"] if isinstance(item, dict))
    return _selector_evidence(candidates[0] if candidates else {})


def _selector_evidence(selector: dict[str, Any]) -> dict[str, str]:
    return {
        "selector_name": str(selector.get("selector_name", selector.get("name", "unknown"))),
        "selector_class": str(selector.get("selector_class", selector.get("class", "unknown"))),
        "selector_location": str(selector.get("selector_location", selector.get("location", "unknown"))),
        "operation_id": str(selector.get("operation_id", "unknown")),
        "path_template": str(selector.get("path_template", "unknown")),
    }


def _context_readiness(design: dict[str, Any]) -> dict[str, Any]:
    approved_context = design.get("approved_context_contract", {}) if isinstance(design.get("approved_context_contract"), dict) else {}
    required = approved_context.get("required_top_level_fields", [])
    required_fields = [str(item) for item in required] if isinstance(required, list) else []
    return {
        "approved_boundary_context_supplied": False,
        "context_schema_version": approved_context.get("schema_version", "adopt_redthread.boundary_probe_context.v1"),
        "required_top_level_fields": required_fields,
        "missing_conditions": [
            "approved_non_production_target",
            "own_scope_actor_label",
            "cross_scope_actor_label",
            "selector_bindings",
            "operator_approval",
        ],
        "storage_policy": approved_context.get("storage_policy", "local_ignored_file_only_never_checked_in"),
    }


def _interpretation(status: str) -> dict[str, Any]:
    mapping = {
        "not_run": {
            "summary": "No boundary execution evidence exists.",
            "gate_effect": "Keep tenant_user_boundary_unproven wording.",
            "confirmed_security_finding": False,
        },
        "passed_boundary_probe": {
            "summary": "Own-scope control worked and cross-scope probe was denied or exposed no data.",
            "gate_effect": "May remove tenant_user_boundary_unproven from evidence gaps, but does not automatically approve write-capable paths.",
            "confirmed_security_finding": False,
        },
        "failed_boundary_probe": {
            "summary": "Cross-scope probe was allowed where denial or no exposure was expected.",
            "gate_effect": "Block until fixed or disproven with stronger approved evidence.",
            "confirmed_security_finding": True,
        },
        "blocked_missing_context": {
            "summary": "Approved target, actor scope, selector binding, auth context, or write context was missing.",
            "gate_effect": "Review; missing context is not a confirmed vulnerability.",
            "confirmed_security_finding": False,
        },
        "auth_or_replay_failed": {
            "summary": "The probe could not be interpreted because auth, replay, host, environment, or policy continuity failed.",
            "gate_effect": "Review or block depending on existing gate policy; not a confirmed vulnerability by itself.",
            "confirmed_security_finding": False,
        },
    }
    return mapping.get(status, mapping["not_run"])


def _gate_decision_for_status(status: str) -> str:
    if status == "failed_boundary_probe":
        return "block"
    if status == "passed_boundary_probe":
        return "review"
    return "review"


def _validate_contract(payload: dict[str, Any]) -> None:
    status = str(payload.get("result_status", ""))
    if status not in RESULT_STATUSES:
        raise ValueError(f"unsupported boundary result_status: {status}")
    for key in ("own_scope_result_class", "cross_scope_result_class"):
        value = str(payload.get(key, ""))
        if value not in ALLOWED_RESULT_CLASSES:
            raise ValueError(f"unsupported {key}: {value}")
    family = str(payload.get("http_status_family", ""))
    if family not in ALLOWED_HTTP_STATUS_FAMILIES:
        raise ValueError(f"unsupported http_status_family: {family}")
    decision = str(payload.get("gate_decision", ""))
    if decision not in {"approve", "review", "block"}:
        raise ValueError(f"unsupported gate_decision: {decision}")
    if status == "failed_boundary_probe" and payload.get("confirmed_security_finding") is not True:
        raise ValueError("failed_boundary_probe must be a confirmed security finding")
    if status != "failed_boundary_probe" and payload.get("confirmed_security_finding") is True:
        raise ValueError("only failed_boundary_probe may be marked as a confirmed security finding")


def _marker_audit(text: str) -> dict[str, Any]:
    lowered = text.casefold()
    marker_hits = [marker for marker in SENSITIVE_MARKERS if marker.casefold() in lowered]
    raw_field_hits = [field for field in FORBIDDEN_RAW_FIELD_KEYS if f'"{field}"' in lowered or f"'{field}'" in lowered]
    return {
        "marker_set": "configured_sensitive_marker_set_plus_boundary_raw_field_keys",
        "marker_count": len(SENSITIVE_MARKERS),
        "marker_hit_count": len(marker_hits),
        "raw_field_key_count": len(FORBIDDEN_RAW_FIELD_KEYS),
        "raw_field_hit_count": len(raw_field_hits),
        "passed": len(marker_hits) == 0 and len(raw_field_hits) == 0,
        "markers": sorted(set(marker_hits)),
        "raw_field_keys": sorted(set(raw_field_hits)),
    }


def _markdown(payload: dict[str, Any]) -> str:
    selector = payload["selector_evidence"]
    readiness = payload["context_readiness"]
    interpretation = payload["interpretation"]
    audit = payload["configured_sensitive_marker_check"]
    notes = payload.get("sanitized_notes", [])
    lines = [
        "# Tenant/User Boundary Probe Result",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Result status: `{payload['result_status']}`",
        f"- Boundary probe executed: `{payload['boundary_probe_executed']}`",
        f"- Gate decision interpretation: `{payload['gate_decision']}`",
        f"- Confirmed security finding: `{payload['confirmed_security_finding']}`",
        f"- Replay failure category: `{payload['replay_failure_category']}`",
        f"- HTTP status family: `{payload['http_status_family']}`",
        f"- This artifact is an executor: `False`",
        f"- Verdict semantics changed: `{payload['verdict_semantics_changed']}`",
        "",
        "## Selector evidence",
        "",
        f"- Selector name: `{selector['selector_name']}`",
        f"- Selector class: `{selector['selector_class']}`",
        f"- Selector location: `{selector['selector_location']}`",
        f"- Operation ID: `{selector['operation_id']}`",
        f"- Path template: `{selector['path_template']}`",
        "",
        "## Result classes",
        "",
        f"- Own-scope result class: `{payload['own_scope_result_class']}`",
        f"- Cross-scope result class: `{payload['cross_scope_result_class']}`",
        "",
        "## Context readiness",
        "",
        f"- Approved boundary context supplied: `{readiness.get('approved_boundary_context_supplied', False)}`",
        f"- Context schema version: `{readiness.get('context_schema_version', 'unknown')}`",
        f"- Missing conditions: `{_join(readiness.get('missing_conditions', []))}`",
        f"- Storage policy: `{readiness.get('storage_policy', 'unknown')}`",
        "",
        "## Interpretation",
        "",
        f"- Summary: {interpretation['summary']}",
        f"- Gate effect: {interpretation['gate_effect']}",
        "- No verdict semantic change is made by recording this artifact; report/matrix surfaces may display it as evidence only.",
        "",
        "## Sanitized notes",
        "",
    ]
    lines.extend(f"- {note}" for note in notes)
    lines.extend([
        "",
        "## Configured sensitive-marker audit",
        "",
        f"- Passed: `{audit['passed']}`",
        f"- Marker hits: `{audit['marker_hit_count']}`",
        f"- Raw field key hits: `{audit['raw_field_hit_count']}`",
        f"- Marker set: `{audit['marker_set']}`",
        "",
    ])
    return "\n".join(lines)


def _load_optional(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _join(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "none"
    return ",".join(str(item) for item in items)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized tenant/user boundary probe result artifact without executing a probe.")
    parser.add_argument("--probe-plan", default=str(DEFAULT_PROBE_PLAN))
    parser.add_argument("--execution-design", default=str(DEFAULT_EXECUTION_DESIGN))
    parser.add_argument("--observed-result", default=None, help="Optional sanitized observed-result JSON to validate and normalize; this script still does not execute probes")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-marker-hit", action="store_true")
    args = parser.parse_args()

    result = build_boundary_probe_result(
        probe_plan=args.probe_plan,
        execution_design=args.execution_design,
        observed_result=args.observed_result,
        output_dir=args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"tenant/user boundary probe result -> {Path(args.output_dir) / 'tenant_user_boundary_probe_result.md'}")
    print(json.dumps({
        "result_status": result["result_status"],
        "boundary_probe_executed": result["boundary_probe_executed"],
        "gate_decision": result["gate_decision"],
        "confirmed_security_finding": result["confirmed_security_finding"],
        "marker_hits": result["configured_sensitive_marker_check"]["marker_hit_count"],
        "raw_field_key_hits": result["configured_sensitive_marker_check"]["raw_field_hit_count"],
    }, indent=2))


if __name__ == "__main__":
    main()

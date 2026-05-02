from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_boundary_probe_context import DEFAULT_OUTPUT_DIR as DEFAULT_CONTEXT_DIR
from scripts.build_boundary_probe_context import FORBIDDEN_RAW_FIELD_KEYS
from scripts.build_boundary_probe_context import SCHEMA_VERSION as CONTEXT_SCHEMA_VERSION
from scripts.build_boundary_probe_context import SENSITIVE_MARKERS

SCHEMA_VERSION = "adopt_redthread.boundary_probe_context_request.v1"
DEFAULT_CONTEXT_INTAKE = DEFAULT_CONTEXT_DIR / "tenant_user_boundary_probe_context.template.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "boundary_probe_context_request"

REQUIRED_CONTEXT_SECTIONS = [
    {
        "section": "target_environment",
        "required_metadata": [
            "environment_label",
            "base_url_label",
            "target_classification=non_production",
            "production=false",
            "approved_for_boundary_probe=true",
        ],
    },
    {
        "section": "actor_scopes",
        "required_metadata": [
            "scope_class",
            "actor_separation_confirmed=true",
            "own_scope actor/tenant labels",
            "cross_scope actor/tenant labels",
        ],
    },
    {
        "section": "selector_bindings",
        "required_metadata": [
            "selector metadata labels",
            "own_scope_value_ref label",
            "cross_scope_value_ref label",
            "separated own/cross value refs",
        ],
    },
    {
        "section": "operator_approval",
        "required_metadata": [
            "approved_by_label",
            "approved_at ISO timestamp",
            "future expires_at ISO timestamp",
            "sanitized scope_note",
        ],
    },
    {
        "section": "safe_execution_constraints",
        "required_metadata": [
            "approved_non_production_only=true",
            "no_raw_values_in_generated_artifacts=true",
            "no_production_writes=true",
            "future_executor_must_not_persist_resolved_values=true",
        ],
    },
]

FORBIDDEN_INPUT_LABELS = [
    "raw actor IDs",
    "raw tenant IDs",
    "raw resource IDs",
    "credentials or session values",
    "auth headers or cookies",
    "request or response bodies",
    "production URLs or production write context",
    "reviewer free-form answers",
]


def build_boundary_probe_context_request(
    *,
    context_intake: str | Path = DEFAULT_CONTEXT_INTAKE,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Build a sanitized request package for approved boundary context metadata.

    This package is a coordination artifact only. It does not execute probes,
    does not resolve values, and does not copy raw context. It tells an operator
    what sanitized metadata is missing before a future approved non-production
    boundary probe can even be considered.
    """

    context_path = Path(context_intake)
    context = _load_json(context_path)
    input_audit = _marker_audit(context_path.read_text(encoding="utf-8") if context_path.exists() else json.dumps(context, sort_keys=True))
    if fail_on_marker_hit and not input_audit["passed"]:
        raise RuntimeError(
            "boundary context request input audit failed "
            f"with markers={input_audit['marker_hit_count']} raw_fields={input_audit['raw_field_hit_count']}"
        )

    validation = context.get("validation", {}) if isinstance(context.get("validation"), dict) else {}
    context_status = str(context.get("context_status", "missing_required_evidence"))
    request_status = _request_status(context, input_audit)
    missing_conditions = _safe_list(validation.get("missing_conditions"))
    blockers = _safe_blockers(validation.get("blockers"))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "request_status": request_status,
        "source_context_intake": _display_path(context_path),
        "source_context_schema_version": context.get("schema_version"),
        "source_context_status": context_status,
        "artifact_policy": (
            "This request package contains only sanitized metadata requirements and validation blocker labels. "
            "It must not contain raw actor, tenant, resource, credential, session, auth-header, cookie, request, response, or write-context values."
        ),
        "boundary_probe_execution_authorized": False,
        "boundary_probe_executed": False,
        "confirmed_security_finding": False,
        "verdict_semantics_changed": False,
        "required_context_schema": CONTEXT_SCHEMA_VERSION,
        "required_context_sections": REQUIRED_CONTEXT_SECTIONS,
        "missing_conditions": missing_conditions,
        "validation_blockers": blockers,
        "sanitized_context_template": _safe_template(context.get("context_template")),
        "forbidden_inputs": FORBIDDEN_INPUT_LABELS,
        "operator_commands": _operator_commands(request_status),
        "acceptance_criteria": _acceptance_criteria(request_status),
        "input_marker_audit": input_audit,
        "non_claims": [
            "This request package is not boundary execution proof.",
            "Supplying ready context is not a confirmed vulnerability and is not release approval.",
            "A future executor must still run only against approved non-production context and write a sanitized result.",
            "This artifact does not change local bridge approve/review/block verdict semantics.",
        ],
    }

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "tenant_user_boundary_probe_context_request.json"
    md_path = output_root / "tenant_user_boundary_probe_context_request.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")

    output_audit = _marker_audit(json.dumps(payload, sort_keys=True) + "\n" + _markdown(payload))
    if fail_on_marker_hit and not output_audit["passed"]:
        raise RuntimeError(
            "boundary context request output audit failed "
            f"with markers={output_audit['marker_hit_count']} raw_fields={output_audit['raw_field_hit_count']}"
        )
    payload["output_marker_audit"] = output_audit
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _request_status(context: dict[str, Any], input_audit: dict[str, Any]) -> str:
    if not input_audit.get("passed", False):
        return "privacy_blocked"
    if context.get("schema_version") in {"missing", "invalid_json", "invalid_shape"}:
        return "missing_required_evidence"
    if context.get("schema_version") != CONTEXT_SCHEMA_VERSION:
        return "missing_required_evidence"
    if context.get("context_status") == "ready_for_boundary_probe":
        return "context_ready"
    return "ready_to_request_context"


def _operator_commands(status: str) -> list[str]:
    if status == "context_ready":
        return [
            "make evidence-boundary-probe-context BOUNDARY_CONTEXT=path/to/sanitized_context.json",
            "make evidence-readiness",
            "make evidence-remediation-queue",
        ]
    if status == "missing_required_evidence":
        return [
            "make evidence-boundary-probe-plan",
            "make evidence-boundary-execution-design",
            "make evidence-boundary-probe-context",
            "make evidence-boundary-context-request",
        ]
    if status == "privacy_blocked":
        return ["regenerate sanitized boundary context artifacts before sharing or using this request package"]
    return [
        "fill a local ignored sanitized context JSON using labels/references only",
        "make evidence-boundary-probe-context BOUNDARY_CONTEXT=path/to/sanitized_context.json",
        "make evidence-boundary-context-request",
        "make evidence-readiness",
        "make evidence-remediation-queue",
    ]


def _acceptance_criteria(status: str) -> list[str]:
    if status == "context_ready":
        return [
            "source context intake remains ready_for_boundary_probe",
            "boundary_probe_executed remains false until a separate approved executor exists",
            "no raw values appear in generated artifacts",
        ]
    return [
        "sanitized context intake reports ready_for_boundary_probe before future execution is considered",
        "target classification is non_production and production is false",
        "operator approval and expiration metadata are present",
        "own/cross actor scopes and selector value references are separated",
        "no raw values appear in generated artifacts",
    ]


def _safe_template(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed_top = ["schema_version", "target_environment", "execution_mode", "actor_scopes", "selector_bindings", "operator_approval", "safe_execution_constraints"]
    shape: dict[str, Any] = {}
    for key in allowed_top:
        if key not in value:
            continue
        if key == "schema_version":
            shape[key] = CONTEXT_SCHEMA_VERSION if value.get(key) == CONTEXT_SCHEMA_VERSION else "schema_version_field_present"
        elif key == "selector_bindings":
            shape[key] = ["selector_binding_metadata_shape"]
        elif isinstance(value.get(key), dict):
            shape[key] = sorted(str(field) for field in value[key].keys())[:20]
        else:
            shape[key] = "field_present"
    return shape


def _safe_blockers(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    blockers: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        blockers.append({"code": str(item.get("code", "unknown")), "detail": _safe_detail(item.get("detail"))})
    return blockers


def _safe_detail(value: Any) -> str:
    text = str(value or "")
    for marker in SENSITIVE_MARKERS:
        if marker.casefold() in text.casefold():
            return "redacted_sensitive_marker_detail"
    return text[:240]


def _safe_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)][:50]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "missing", "load_error": "missing_file", "path": _display_path(path)}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": "invalid_json", "load_error": "invalid_json", "path": _display_path(path)}
    return loaded if isinstance(loaded, dict) else {"schema_version": "invalid_shape", "load_error": "json_not_object", "path": _display_path(path)}


def _marker_audit(text: str) -> dict[str, Any]:
    lowered = text.casefold()
    marker_hits = [marker for marker in SENSITIVE_MARKERS if marker.casefold() in lowered]
    raw_field_hits = [field for field in FORBIDDEN_RAW_FIELD_KEYS if f'"{field}"' in lowered or f"'{field}'" in lowered]
    return {
        "marker_set": "configured_sensitive_marker_set_plus_boundary_context_raw_field_keys",
        "marker_count": len(SENSITIVE_MARKERS),
        "marker_hit_count": len(marker_hits),
        "raw_field_key_count": len(FORBIDDEN_RAW_FIELD_KEYS),
        "raw_field_hit_count": len(raw_field_hits),
        "passed": len(marker_hits) == 0 and len(raw_field_hits) == 0,
        "markers": ["redacted_configured_marker"] if marker_hits else [],
        "raw_field_keys": ["redacted_raw_field_key"] if raw_field_hits else [],
    }


def _markdown(payload: dict[str, Any]) -> str:
    output_audit = payload.get("output_marker_audit", {"passed": "pending", "marker_hit_count": "pending", "raw_field_hit_count": "pending"})
    lines = [
        "# Tenant/User Boundary Probe Context Request",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Request status: `{payload['request_status']}`",
        f"- Source context status: `{payload.get('source_context_status')}`",
        f"- Boundary probe execution authorized by this request: `{payload['boundary_probe_execution_authorized']}`",
        f"- Boundary probe executed: `{payload['boundary_probe_executed']}`",
        f"- Confirmed security finding: `{payload['confirmed_security_finding']}`",
        f"- Verdict semantics changed: `{payload['verdict_semantics_changed']}`",
        "",
        "## Missing conditions",
        "",
    ]
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- `{item}`" for item in missing) if missing else lines.append("- none")
    lines.extend(["", "## Validation blockers", ""])
    blockers = payload.get("validation_blockers", [])
    if blockers:
        lines.extend(f"- `{item.get('code', 'unknown')}` — {item.get('detail', '')}" for item in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Required sanitized context sections", ""])
    for section in payload.get("required_context_sections", []):
        lines.append(f"### `{section['section']}`")
        lines.extend(f"- {item}" for item in section.get("required_metadata", []))
        lines.append("")
    lines.extend(["## Forbidden inputs", ""])
    lines.extend(f"- {item}" for item in payload.get("forbidden_inputs", []))
    lines.extend(["", "## Operator commands", ""])
    lines.extend(f"- `{command}`" for command in payload.get("operator_commands", []))
    lines.extend(["", "## Acceptance criteria", ""])
    lines.extend(f"- {item}" for item in payload.get("acceptance_criteria", []))
    lines.extend([
        "",
        "## Marker audit",
        "",
        f"- Input passed: `{payload['input_marker_audit']['passed']}`",
        f"- Input marker hits: `{payload['input_marker_audit']['marker_hit_count']}`",
        f"- Input raw field key hits: `{payload['input_marker_audit']['raw_field_hit_count']}`",
        f"- Output passed: `{output_audit['passed']}`",
        f"- Output marker hits: `{output_audit['marker_hit_count']}`",
        f"- Output raw field key hits: `{output_audit['raw_field_hit_count']}`",
        "",
        "## Non-claims",
        "",
    ])
    lines.extend(f"- {claim}" for claim in payload.get("non_claims", []))
    lines.append("")
    return "\n".join(lines)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized request package for approved tenant/user boundary context metadata without executing probes.")
    parser.add_argument("--context-intake", default=str(DEFAULT_CONTEXT_INTAKE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-marker-hit", action="store_true")
    args = parser.parse_args()
    payload = build_boundary_probe_context_request(
        context_intake=args.context_intake,
        output_dir=args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"tenant/user boundary probe context request -> {Path(args.output_dir) / 'tenant_user_boundary_probe_context_request.md'}")
    print(json.dumps({
        "request_status": payload["request_status"],
        "source_context_status": payload["source_context_status"],
        "missing_conditions": payload["missing_conditions"],
        "input_marker_hits": payload["input_marker_audit"]["marker_hit_count"],
        "raw_field_key_hits": payload["input_marker_audit"]["raw_field_hit_count"],
    }, indent=2))


if __name__ == "__main__":
    main()

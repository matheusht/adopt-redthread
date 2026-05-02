from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_boundary_probe_context_request import DEFAULT_OUTPUT_DIR as DEFAULT_BOUNDARY_CONTEXT_REQUEST_DIR
from scripts.build_boundary_probe_context_request import build_boundary_probe_context_request
from scripts.build_evidence_freshness_manifest import DEFAULT_OUTPUT_DIR as DEFAULT_FRESHNESS_DIR
from scripts.build_evidence_freshness_manifest import build_evidence_freshness_manifest
from scripts.build_external_review_return_ledger import DEFAULT_OUTPUT_DIR as DEFAULT_RETURNS_DIR
from scripts.build_external_review_return_ledger import build_external_review_return_ledger
from scripts.build_reviewer_packet import audit_sanitized_markdown

SCHEMA_VERSION = "adopt_redthread.evidence_readiness.v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "evidence_readiness"
DEFAULT_EVIDENCE_MATRIX = REPO_ROOT / "runs" / "evidence_matrix" / "evidence_matrix.json"
DEFAULT_REVIEWER_PACKET = REPO_ROOT / "runs" / "reviewer_packet" / "reviewer_packet.json"
DEFAULT_HANDOFF_MANIFEST = REPO_ROOT / "runs" / "external_review_handoff" / "external_review_handoff_manifest.json"
DEFAULT_SESSION_BATCH = REPO_ROOT / "runs" / "external_review_sessions" / "external_review_session_batch.json"
DEFAULT_VALIDATION_READOUT = REPO_ROOT / "runs" / "external_validation_readout" / "external_validation_readout.json"
DEFAULT_EXTERNAL_REVIEW_RETURNS = DEFAULT_RETURNS_DIR / "external_review_return_ledger.json"
DEFAULT_BOUNDARY_CONTEXT = REPO_ROOT / "runs" / "boundary_probe_context" / "tenant_user_boundary_probe_context.template.json"
DEFAULT_BOUNDARY_CONTEXT_REQUEST = DEFAULT_BOUNDARY_CONTEXT_REQUEST_DIR / "tenant_user_boundary_probe_context_request.json"
DEFAULT_BOUNDARY_RESULT = REPO_ROOT / "runs" / "boundary_probe_result" / "tenant_user_boundary_probe_result.json"
DEFAULT_FRESHNESS_MANIFEST = DEFAULT_FRESHNESS_DIR / "evidence_freshness_manifest.json"

REQUIRED_SCHEMAS = {
    "evidence_matrix": "adopt_redthread.evidence_matrix.v1",
    "reviewer_packet": "adopt_redthread.reviewer_packet.v1",
    "external_review_handoff": "adopt_redthread.external_review_handoff.v1",
    "external_review_session_batch": "adopt_redthread.external_review_session_batch.v1",
    "external_validation_readout": "adopt_redthread.external_validation_readout.v1",
    "external_review_returns": "adopt_redthread.external_review_return_ledger.v1",
    "boundary_probe_context": "adopt_redthread.boundary_probe_context.v1",
    "boundary_probe_context_request": "adopt_redthread.boundary_probe_context_request.v1",
    "boundary_probe_result": "adopt_redthread.boundary_probe_result.v1",
    "evidence_freshness": "adopt_redthread.evidence_freshness_manifest.v1",
}


def build_evidence_readiness(
    *,
    evidence_matrix: str | Path = DEFAULT_EVIDENCE_MATRIX,
    reviewer_packet: str | Path = DEFAULT_REVIEWER_PACKET,
    handoff_manifest: str | Path = DEFAULT_HANDOFF_MANIFEST,
    session_batch: str | Path = DEFAULT_SESSION_BATCH,
    validation_readout: str | Path = DEFAULT_VALIDATION_READOUT,
    external_review_returns: str | Path = DEFAULT_EXTERNAL_REVIEW_RETURNS,
    boundary_context: str | Path = DEFAULT_BOUNDARY_CONTEXT,
    boundary_context_request: str | Path = DEFAULT_BOUNDARY_CONTEXT_REQUEST,
    boundary_result: str | Path = DEFAULT_BOUNDARY_RESULT,
    freshness_manifest: str | Path = DEFAULT_FRESHNESS_MANIFEST,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    regenerate_freshness: bool = True,
    regenerate_external_review_returns: bool = True,
    regenerate_boundary_context_request: bool = True,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Build a one-page local evidence readiness ledger.

    This is an index over sanitized generated artifacts. It is not a release gate,
    not external validation, not boundary execution, and not a change to bridge
    approve/review/block semantics.
    """

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    matrix_path = Path(evidence_matrix)
    packet_path = Path(reviewer_packet)
    handoff_path = Path(handoff_manifest)
    batch_path = Path(session_batch)
    readout_path = Path(validation_readout)
    returns_path = Path(external_review_returns)
    boundary_context_path = Path(boundary_context)
    boundary_context_request_path = Path(boundary_context_request)
    boundary_path = Path(boundary_result)
    freshness_path = Path(freshness_manifest)

    if regenerate_freshness:
        freshness = build_evidence_freshness_manifest(
            reviewer_packet=packet_path,
            handoff_manifest=handoff_path,
            session_batch=batch_path,
            output_dir=freshness_path.parent,
            fail_on_marker_hit=fail_on_marker_hit,
        )
        freshness_path = freshness_path.parent / "evidence_freshness_manifest.json"
    else:
        freshness = _load_json(freshness_path)

    if regenerate_external_review_returns:
        returns = build_external_review_return_ledger(
            output_dir=returns_path.parent,
            fail_on_marker_hit=fail_on_marker_hit,
        )
        returns_path = returns_path.parent / "external_review_return_ledger.json"
    else:
        returns = _load_json(returns_path)

    if regenerate_boundary_context_request:
        request = build_boundary_probe_context_request(
            context_intake=boundary_context_path,
            output_dir=boundary_context_request_path.parent,
            fail_on_marker_hit=fail_on_marker_hit,
        )
        boundary_context_request_path = boundary_context_request_path.parent / "tenant_user_boundary_probe_context_request.json"
    else:
        request = _load_json(boundary_context_request_path)

    matrix = _load_json(matrix_path)
    packet = _load_json(packet_path)
    handoff = _load_json(handoff_path)
    batch = _load_json(batch_path)
    readout = _load_json(readout_path)
    boundary_context_payload = _load_json(boundary_context_path)
    boundary = _load_json(boundary_path)

    marker_audits = _collect_marker_audits(packet, handoff, batch, readout, returns, boundary_context_payload, request, boundary, freshness)
    generated_paths = [matrix_path, packet_path, handoff_path, batch_path, readout_path, returns_path, boundary_context_path, boundary_context_request_path, boundary_path, freshness_path]
    local_audit = _safe_marker_audit(audit_sanitized_markdown([path for path in generated_paths if path.exists()]))
    marker_audits.append({"label": "readiness_input_files", **local_audit})
    if fail_on_marker_hit and any((not audit.get("passed", False)) or int(audit.get("marker_hit_count", 0) or 0) for audit in marker_audits):
        hit_count = sum(int(audit.get("marker_hit_count", 0) or 0) for audit in marker_audits)
        failed_count = sum(1 for audit in marker_audits if not audit.get("passed", False))
        raise RuntimeError(f"readiness marker audit failed with {hit_count} hits across {failed_count} failed audits")

    components = {
        "evidence_matrix": _matrix_component(matrix_path, matrix),
        "reviewer_packet": _schema_component(packet_path, packet, "reviewer_packet"),
        "external_review_handoff": _handoff_component(handoff_path, handoff),
        "external_review_sessions": _session_component(batch_path, batch),
        "external_validation_readout": _readout_component(readout_path, readout),
        "external_review_returns": _returns_component(returns_path, returns),
        "boundary_probe_context": _boundary_context_component(boundary_context_path, boundary_context_payload),
        "boundary_probe_context_request": _boundary_context_request_component(boundary_context_request_path, request),
        "boundary_probe_result": _boundary_component(boundary_path, boundary),
        "evidence_freshness": _freshness_component(freshness_path, freshness),
    }
    blockers = _blockers(components, marker_audits)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "readiness_status": _readiness_status(blockers),
        "artifact_policy": "Readiness is derived from sanitized generated evidence metadata only. It must not include raw HAR/session/cookie/auth/header/body/request/response data, source files, or write-context values.",
        "components": components,
        "blockers": blockers,
        "marker_audits": marker_audits,
        "recommended_next_actions": _recommended_next_actions(blockers, components),
        "non_claims": [
            "This readiness ledger is not a production publish approval.",
            "This readiness ledger is not external human validation until filled external observations are summarized.",
            "This readiness ledger is not boundary execution proof.",
            "This readiness ledger does not prove buyer demand, production readiness, or whole-app safety.",
            "This readiness ledger does not change local bridge approve/review/block verdict semantics.",
        ],
    }
    (output_root / "evidence_readiness.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output_root / "evidence_readiness.md").write_text(_markdown(payload), encoding="utf-8")
    return payload


def _matrix_component(path: Path, matrix: dict[str, Any]) -> dict[str, Any]:
    rows = matrix.get("rows", []) if isinstance(matrix.get("rows"), list) else []
    decisions: dict[str, int] = {"approve": 0, "review": 0, "block": 0}
    for row in rows:
        if isinstance(row, dict):
            decision = str(row.get("gate_decision") or row.get("outcome_slot") or "unknown")
            decisions[decision] = decisions.get(decision, 0) + 1
    required = {"approve", "review", "block"}
    present = {key for key, value in decisions.items() if value and key in required}
    return {
        **_schema_component(path, matrix, "evidence_matrix"),
        "row_count": len(rows),
        "decision_counts": decisions,
        "has_approve_review_block_examples": required.issubset(present),
    }


def _handoff_component(path: Path, handoff: dict[str, Any]) -> dict[str, Any]:
    component = _schema_component(path, handoff, "external_review_handoff")
    component.update({
        "handoff_status": handoff.get("handoff_status"),
        "validation_status": handoff.get("validation_status"),
        "target_review_count": handoff.get("target_review_count"),
        "allowed_artifact_count": len(handoff.get("protocol", {}).get("allowed_artifacts", [])) if isinstance(handoff.get("protocol"), dict) else 0,
    })
    return component


def _session_component(path: Path, batch: dict[str, Any]) -> dict[str, Any]:
    sessions = batch.get("sessions", []) if isinstance(batch.get("sessions"), list) else []
    component = _schema_component(path, batch, "external_review_session_batch")
    component.update({
        "session_status": batch.get("session_status"),
        "validation_status": batch.get("validation_status"),
        "session_count": len(sessions),
        "target_review_count": batch.get("target_review_count"),
    })
    return component


def _readout_component(path: Path, readout: dict[str, Any]) -> dict[str, Any]:
    rollup = readout.get("rollup_summary", {}) if isinstance(readout.get("rollup_summary"), dict) else {}
    component = _schema_component(path, readout, "external_validation_readout")
    component.update({
        "readout_status": readout.get("readout_status"),
        "validation_claim": readout.get("validation_claim"),
        "complete_summary_count": rollup.get("complete_summary_count", 0),
        "target_review_count": readout.get("target_review_count"),
        "missing_or_invalid_summary_count": rollup.get("missing_or_invalid_file_count", 0),
    })
    return component


def _returns_component(path: Path, returns: dict[str, Any]) -> dict[str, Any]:
    summary = returns.get("summary", {}) if isinstance(returns.get("summary"), dict) else {}
    coverage = returns.get("review_input_coverage", {}) if isinstance(returns.get("review_input_coverage"), dict) else {}
    component = _schema_component(path, returns, "external_review_returns")
    component.update({
        "ledger_status": returns.get("ledger_status"),
        "complete_count": summary.get("complete_count", 0),
        "session_count": summary.get("session_count", 0),
        "missing_summary_count": summary.get("missing_summary_count", 0),
        "invalid_summary_count": summary.get("invalid_summary_count", 0),
        "incomplete_summary_count": summary.get("incomplete_summary_count", 0),
        "decision_followup_count": summary.get("decision_followup_count", 0),
        "privacy_blocked_count": summary.get("privacy_blocked_count", 0),
        "boundary_context_request_delivery_status": coverage.get("boundary_context_request_delivery_status"),
        "boundary_context_request_delivered_session_count": coverage.get("delivered_session_count", 0),
        "boundary_context_request_is_approved_context": bool(coverage.get("boundary_context_request_is_approved_context", False)),
        "boundary_context_request_is_execution_proof": bool(coverage.get("boundary_context_request_is_execution_proof", False)),
    })
    return component


def _boundary_context_component(path: Path, context: dict[str, Any]) -> dict[str, Any]:
    validation = context.get("validation", {}) if isinstance(context.get("validation"), dict) else {}
    component = _schema_component(path, context, "boundary_probe_context")
    component.update({
        "context_status": context.get("context_status"),
        "boundary_probe_execution_authorized": bool(context.get("boundary_probe_execution_authorized", False)),
        "boundary_probe_executed": bool(context.get("boundary_probe_executed", False)),
        "gate_decision": context.get("gate_decision"),
        "confirmed_security_finding": bool(context.get("confirmed_security_finding", False)),
        "verdict_semantics_changed": bool(context.get("verdict_semantics_changed", False)),
        "validation_valid": bool(validation.get("valid", False)),
        "validation_blocker_count": int(validation.get("blocker_count", 0) or 0),
    })
    return component


def _boundary_context_request_component(path: Path, request: dict[str, Any]) -> dict[str, Any]:
    blockers = request.get("validation_blockers", []) if isinstance(request.get("validation_blockers"), list) else []
    missing_conditions = request.get("missing_conditions", []) if isinstance(request.get("missing_conditions"), list) else []
    component = _schema_component(path, request, "boundary_probe_context_request")
    component.update({
        "request_status": request.get("request_status"),
        "source_context_status": request.get("source_context_status"),
        "boundary_probe_execution_authorized": bool(request.get("boundary_probe_execution_authorized", False)),
        "boundary_probe_executed": bool(request.get("boundary_probe_executed", False)),
        "confirmed_security_finding": bool(request.get("confirmed_security_finding", False)),
        "verdict_semantics_changed": bool(request.get("verdict_semantics_changed", False)),
        "missing_condition_count": len(missing_conditions),
        "validation_blocker_count": len(blockers),
    })
    return component


def _boundary_component(path: Path, boundary: dict[str, Any]) -> dict[str, Any]:
    component = _schema_component(path, boundary, "boundary_probe_result")
    component.update({
        "result_status": boundary.get("result_status"),
        "boundary_probe_executed": bool(boundary.get("boundary_probe_executed", False)),
        "gate_decision": boundary.get("gate_decision"),
        "confirmed_security_finding": bool(boundary.get("confirmed_security_finding", False)),
        "verdict_semantics_changed": bool(boundary.get("verdict_semantics_changed", False)),
    })
    return component


def _freshness_component(path: Path, freshness: dict[str, Any]) -> dict[str, Any]:
    summary = freshness.get("summary", {}) if isinstance(freshness.get("summary"), dict) else {}
    component = _schema_component(path, freshness, "evidence_freshness")
    component.update({
        "freshness_status": freshness.get("freshness_status"),
        "copy_check_count": summary.get("copy_check_count", 0),
        "problem_count": summary.get("problem_count", 0),
    })
    return component


def _schema_component(path: Path, payload: dict[str, Any], schema_key: str) -> dict[str, Any]:
    expected = REQUIRED_SCHEMAS[schema_key]
    return {
        "path": _display_path(path),
        "exists": path.exists(),
        "schema_version": payload.get("schema_version"),
        "schema_valid": payload.get("schema_version") == expected,
    }


def _blockers(components: dict[str, dict[str, Any]], marker_audits: list[dict[str, Any]]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for label, component in components.items():
        if not component.get("exists"):
            blockers.append({"code": "missing_required_evidence", "component": label, "detail": "artifact is missing"})
        elif not component.get("schema_valid"):
            blockers.append({"code": "invalid_required_evidence_schema", "component": label, "detail": str(component.get("schema_version"))})
    if any(not audit.get("passed", False) or int(audit.get("marker_hit_count", 0) or 0) for audit in marker_audits):
        blockers.append({"code": "privacy_marker_audit_failed", "component": "marker_audits", "detail": "configured sensitive-marker audit did not pass"})
    freshness = components["evidence_freshness"]
    if freshness.get("schema_valid") and freshness.get("freshness_status") != "fresh":
        blockers.append({"code": "stale_or_missing_evidence_copies", "component": "evidence_freshness", "detail": str(freshness.get("freshness_status"))})
    readout = components["external_validation_readout"]
    if readout.get("schema_valid") and readout.get("readout_status") != "ready_for_external_validation_readout":
        blockers.append({"code": "external_validation_not_ready", "component": "external_validation_readout", "detail": str(readout.get("readout_status"))})
    returns = components["external_review_returns"]
    if returns.get("schema_valid") and returns.get("ledger_status") != "ready_for_external_validation_readout":
        blockers.append({"code": "external_review_returns_not_ready", "component": "external_review_returns", "detail": str(returns.get("ledger_status"))})
    boundary_context = components["boundary_probe_context"]
    if boundary_context.get("schema_valid") and boundary_context.get("context_status") != "ready_for_boundary_probe":
        blockers.append({"code": "boundary_context_not_ready", "component": "boundary_probe_context", "detail": str(boundary_context.get("context_status"))})
    boundary_request = components["boundary_probe_context_request"]
    if boundary_request.get("schema_valid") and boundary_request.get("request_status") not in {"ready_to_request_context", "context_ready"}:
        blockers.append({"code": "boundary_context_request_not_ready", "component": "boundary_probe_context_request", "detail": str(boundary_request.get("request_status"))})
    boundary = components["boundary_probe_result"]
    if boundary.get("schema_valid") and not boundary.get("boundary_probe_executed"):
        blockers.append({"code": "boundary_probe_not_executed", "component": "boundary_probe_result", "detail": str(boundary.get("result_status"))})
    if components["evidence_matrix"].get("schema_valid") and not components["evidence_matrix"].get("has_approve_review_block_examples"):
        blockers.append({"code": "matrix_missing_decision_examples", "component": "evidence_matrix", "detail": "approve/review/block examples are not all present"})
    return blockers


def _readiness_status(blockers: list[dict[str, str]]) -> str:
    codes = {blocker["code"] for blocker in blockers}
    if "privacy_marker_audit_failed" in codes:
        return "privacy_blocked"
    if "missing_required_evidence" in codes or "invalid_required_evidence_schema" in codes:
        return "missing_required_evidence"
    if "stale_or_missing_evidence_copies" in codes:
        return "stale_or_missing_evidence"
    if "external_validation_not_ready" in codes or "external_review_returns_not_ready" in codes:
        return "waiting_for_external_validation"
    if "boundary_context_not_ready" in codes or "boundary_context_request_not_ready" in codes:
        return "boundary_context_pending"
    if "boundary_probe_not_executed" in codes:
        return "boundary_context_pending"
    if "matrix_missing_decision_examples" in codes:
        return "needs_decision_example_coverage"
    return "ready_for_sanitized_readout"


def _recommended_next_actions(blockers: list[dict[str, str]], components: dict[str, dict[str, Any]]) -> list[str]:
    codes = {blocker["code"] for blocker in blockers}
    actions: list[str] = []
    if "missing_required_evidence" in codes or "invalid_required_evidence_schema" in codes:
        actions.append("Regenerate the required sanitized evidence artifacts before review.")
    if "privacy_marker_audit_failed" in codes:
        actions.append("Remove or regenerate artifacts that hit configured sensitive-marker checks before sharing any packet.")
    if "stale_or_missing_evidence_copies" in codes:
        actions.append("Regenerate handoff/session artifacts so copied reviewer evidence hashes match their sanitized sources.")
    if "external_validation_not_ready" in codes:
        remaining = components["external_validation_readout"].get("target_review_count") or 3
        complete = components["external_validation_readout"].get("complete_summary_count") or 0
        actions.append(f"Collect and summarize external reviewer observations until complete summaries reach {remaining}; current complete summaries: {complete}.")
    elif "external_review_returns_not_ready" in codes:
        returns = components.get("external_review_returns", {})
        actions.append(f"Resolve external reviewer return ledger blockers before claiming external validation; current ledger status: {returns.get('ledger_status')}.")
    if "boundary_context_not_ready" in codes:
        status = components["boundary_probe_context"].get("context_status")
        request_status = components.get("boundary_probe_context_request", {}).get("request_status")
        actions.append(f"Validate sanitized approved non-production boundary context before any future execution; current context status: {status}; context request status: {request_status}.")
    if "boundary_context_request_not_ready" in codes:
        request_status = components.get("boundary_probe_context_request", {}).get("request_status")
        actions.append(f"Regenerate the sanitized boundary context request package before asking an operator for context; current request status: {request_status}.")
    if "boundary_probe_not_executed" in codes:
        context_status = components.get("boundary_probe_context", {}).get("context_status")
        if context_status == "ready_for_boundary_probe":
            actions.append("Boundary context is ready, but no boundary probe has executed; do not treat ready context as execution proof.")
        else:
            actions.append("Keep boundary execution blocked until approved non-production tenant/user context exists; do not treat missing context as a confirmed vulnerability.")
    if "matrix_missing_decision_examples" in codes:
        actions.append("Regenerate the evidence matrix with approve, review, and block examples present.")
    if not actions:
        actions.append("Review the sanitized readout; do not treat it as buyer-demand, production-readiness, or whole-app safety proof.")
    return actions


def _safe_marker_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "checked_files": audit.get("checked_files", []),
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(audit.get("markers_checked", [])) or audit.get("marker_count", 0),
        "marker_hit_count": audit.get("marker_hit_count", 0),
        "passed": audit.get("passed", False),
        "hit_files": sorted({str(hit.get("file")) for hit in audit.get("hits", []) if isinstance(hit, dict)}) or audit.get("hit_files", []),
    }


def _collect_marker_audits(*payloads: dict[str, Any]) -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for label in (
            "sanitized_marker_audit",
            "input_marker_audit",
            "output_marker_audit",
            "configured_sensitive_marker_check",
        ):
            audit = payload.get(label)
            if isinstance(audit, dict):
                audits.append({"label": label, **audit})
    return audits


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "missing", "load_error": "missing_file", "path": _display_path(path)}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": "invalid_json", "load_error": "invalid_json", "path": _display_path(path)}
    return loaded if isinstance(loaded, dict) else {"schema_version": "invalid_shape", "load_error": "json_not_object", "path": _display_path(path)}


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Evidence Readiness Ledger",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Readiness status: `{payload['readiness_status']}`",
        f"- Blocker count: `{len(payload['blockers'])}`",
        "",
        "## Components",
        "",
        "| Component | Exists | Schema valid | Status detail |",
        "|---|---:|---:|---|",
    ]
    for label, component in payload["components"].items():
        lines.append(f"| `{label}` | `{component.get('exists')}` | `{component.get('schema_valid')}` | `{_component_detail(label, component)}` |")
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}` on `{blocker['component']}`: {blocker['detail']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Recommended next actions", ""])
    lines.extend(f"- {action}" for action in payload["recommended_next_actions"])
    lines.extend(["", "## Non-claims", ""])
    lines.extend(f"- {claim}" for claim in payload["non_claims"])
    lines.append("")
    return "\n".join(lines)


def _component_detail(label: str, component: dict[str, Any]) -> str:
    if label == "evidence_matrix":
        return f"rows:{component.get('row_count', 0)} decisions:{component.get('decision_counts', {})}"
    if label == "external_validation_readout":
        return f"status:{component.get('readout_status')} complete:{component.get('complete_summary_count')}/{component.get('target_review_count')}"
    if label == "external_review_returns":
        return f"status:{component.get('ledger_status')} complete:{component.get('complete_count')}/{component.get('session_count')} context_request:{component.get('boundary_context_request_delivery_status')}"
    if label == "boundary_probe_context":
        return f"status:{component.get('context_status')} authorized:{component.get('boundary_probe_execution_authorized')} blockers:{component.get('validation_blocker_count')}"
    if label == "boundary_probe_context_request":
        return f"status:{component.get('request_status')} source_context:{component.get('source_context_status')} missing:{component.get('missing_condition_count')} blockers:{component.get('validation_blocker_count')}"
    if label == "boundary_probe_result":
        return f"status:{component.get('result_status')} executed:{component.get('boundary_probe_executed')} finding:{component.get('confirmed_security_finding')}"
    if label == "evidence_freshness":
        return f"status:{component.get('freshness_status')} problems:{component.get('problem_count')}"
    if label == "external_review_sessions":
        return f"status:{component.get('session_status')} sessions:{component.get('session_count')}/{component.get('target_review_count')}"
    if label == "external_review_handoff":
        return f"status:{component.get('handoff_status')} validation:{component.get('validation_status')}"
    return str(component.get("schema_version"))


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized evidence readiness ledger from generated reviewer evidence metadata.")
    parser.add_argument("--evidence-matrix", default=str(DEFAULT_EVIDENCE_MATRIX))
    parser.add_argument("--reviewer-packet", default=str(DEFAULT_REVIEWER_PACKET))
    parser.add_argument("--handoff-manifest", default=str(DEFAULT_HANDOFF_MANIFEST))
    parser.add_argument("--session-batch", default=str(DEFAULT_SESSION_BATCH))
    parser.add_argument("--validation-readout", default=str(DEFAULT_VALIDATION_READOUT))
    parser.add_argument("--external-review-returns", default=str(DEFAULT_EXTERNAL_REVIEW_RETURNS))
    parser.add_argument("--boundary-context", default=str(DEFAULT_BOUNDARY_CONTEXT))
    parser.add_argument("--boundary-context-request", default=str(DEFAULT_BOUNDARY_CONTEXT_REQUEST))
    parser.add_argument("--boundary-result", default=str(DEFAULT_BOUNDARY_RESULT))
    parser.add_argument("--freshness-manifest", default=str(DEFAULT_FRESHNESS_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--skip-regenerate-freshness", action="store_true")
    parser.add_argument("--skip-regenerate-external-review-returns", action="store_true")
    parser.add_argument("--skip-regenerate-boundary-context-request", action="store_true")
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if configured sensitive markers are present (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write the ledger even when configured sensitive markers are present")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()
    payload = build_evidence_readiness(
        evidence_matrix=args.evidence_matrix,
        reviewer_packet=args.reviewer_packet,
        handoff_manifest=args.handoff_manifest,
        session_batch=args.session_batch,
        validation_readout=args.validation_readout,
        external_review_returns=args.external_review_returns,
        boundary_context=args.boundary_context,
        boundary_context_request=args.boundary_context_request,
        boundary_result=args.boundary_result,
        freshness_manifest=args.freshness_manifest,
        output_dir=args.output_dir,
        regenerate_freshness=not args.skip_regenerate_freshness,
        regenerate_external_review_returns=not args.skip_regenerate_external_review_returns,
        regenerate_boundary_context_request=not args.skip_regenerate_boundary_context_request,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"evidence readiness ledger -> {Path(args.output_dir) / 'evidence_readiness.md'}")
    print(json.dumps({
        "readiness_status": payload["readiness_status"],
        "blocker_count": len(payload["blockers"]),
        "recommended_next_actions": payload["recommended_next_actions"],
    }, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_reviewer_packet import audit_sanitized_markdown

SCHEMA_VERSION = "adopt_redthread.external_review_return_ledger.v1"
DISTRIBUTION_SCHEMA = "adopt_redthread.external_review_distribution_manifest.v1"
SUMMARY_SCHEMA = "adopt_redthread.reviewer_observation_summary.v1"
DEFAULT_DISTRIBUTION = REPO_ROOT / "runs" / "external_review_distribution" / "external_review_distribution_manifest.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "external_review_returns"
BOUNDARY_CONTEXT_REQUEST_FILENAME = "tenant_user_boundary_probe_context_request.md"


def build_external_review_return_ledger(
    *,
    distribution_manifest: str | Path = DEFAULT_DISTRIBUTION,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Build a sanitized per-reviewer return/follow-up ledger.

    The ledger reads the external review distribution manifest and expected
    reviewer_observation_summary JSON files only. It does not read filled raw
    observation markdown, raw app artifacts, source files, credentials,
    request/response bodies, write-context values, or boundary values. It copies
    only per-review status metadata, never reviewer free-form answers.
    """

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    distribution_path = Path(distribution_manifest)
    distribution = _load_json(distribution_path)
    deliveries = _deliveries(distribution)
    summary_paths = [_resolve_path(delivery.get("expected_summary_path")) for delivery in deliveries if delivery.get("expected_summary_path")]

    input_paths = [path for path in [distribution_path, *summary_paths] if path.exists()]
    input_audit = _safe_audit(audit_sanitized_markdown(_dedupe_paths(input_paths)))
    sessions = [_session_return(delivery) for delivery in deliveries]
    embedded_marker_hit_count = sum(int(session.get("summary_marker_hit_count", 0) or 0) for session in sessions)
    marker_hit_count = int(input_audit.get("marker_hit_count", 0) or 0) + embedded_marker_hit_count
    if fail_on_marker_hit and marker_hit_count:
        raise RuntimeError(f"external review return ledger marker audit failed with {marker_hit_count} hits")

    schema_check = _schema_check(distribution_path, distribution, DISTRIBUTION_SCHEMA)
    blockers = _blockers(schema_check, distribution, input_audit, sessions)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "ledger_status": _ledger_status(schema_check, blockers, sessions),
        "artifact_policy": "Return ledger reads the distribution manifest and sanitized reviewer_observation_summary JSON files only. It does not read filled observation markdown or copy reviewer free-form answers.",
        "distribution_manifest": _display_path(distribution_path),
        "distribution_schema_valid": schema_check["schema_valid"],
        "distribution_status": distribution.get("distribution_status"),
        "target_review_count": distribution.get("target_review_count") or len(deliveries),
        "summary": _summary(sessions),
        "review_input_coverage": _review_input_coverage(deliveries),
        "sessions": sessions,
        "blockers": blockers,
        "input_marker_audit": input_audit,
        "commands": _commands(sessions),
        "non_claims": [
            "A return ledger is operational tracking, not external validation.",
            "Missing, incomplete, or follow-up-needed returns are not release approval or validation failure by themselves.",
            "This ledger does not include raw reviewer answers.",
            "This ledger does not prove buyer demand, production readiness, boundary execution, or whole-app safety.",
            "This ledger does not change local bridge approve/review/block verdict semantics.",
        ],
    }
    json_path = output_root / "external_review_return_ledger.json"
    md_path = output_root / "external_review_return_ledger.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")

    output_audit = _safe_audit(audit_sanitized_markdown([json_path, md_path]))
    if fail_on_marker_hit and output_audit["marker_hit_count"]:
        raise RuntimeError(f"external review return ledger output marker audit failed with {output_audit['marker_hit_count']} hits")
    payload["output_marker_audit"] = output_audit
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _session_return(delivery: dict[str, Any]) -> dict[str, Any]:
    summary_path = _resolve_path(delivery.get("expected_summary_path"))
    summary = _load_json(summary_path)
    schema_valid = summary.get("schema_version") == SUMMARY_SCHEMA
    completion = summary.get("completion_summary", {}) if isinstance(summary.get("completion_summary"), dict) else {}
    signals = summary.get("validation_signals", {}) if isinstance(summary.get("validation_signals"), dict) else {}
    audit = summary.get("sanitized_marker_audit", {}) if isinstance(summary.get("sanitized_marker_audit"), dict) else {}
    complete = bool(completion.get("complete", False))
    release_decision = _decision_label(signals.get("release_decision", "unrecorded"))
    decision_consistency = str(signals.get("decision_consistency", "unknown"))
    marker_hit_count = int(audit.get("marker_hit_count", 0) or 0) if schema_valid else 0
    marker_passed = bool(audit.get("passed", False)) if schema_valid else False

    return_status = _return_status(
        exists=summary_path.exists(),
        parse_error=str(summary.get("load_error", "")),
        schema_valid=schema_valid,
        complete=complete,
        marker_hit_count=marker_hit_count,
        marker_passed=marker_passed,
        release_decision=release_decision,
        decision_consistency=decision_consistency,
    )
    return {
        "session_id": str(delivery.get("session_id", "unknown_session")),
        "session_dir": delivery.get("session_dir"),
        "summary_path": _display_path(summary_path),
        "summary_exists": summary_path.exists(),
        "summary_schema_valid": schema_valid,
        "parse_error": summary.get("load_error", ""),
        "return_status": return_status,
        "complete": complete,
        "missing_field_count": _safe_int(completion.get("missing_field_count"), default=0),
        "missing_silent_question_count": _safe_int(completion.get("missing_silent_question_count"), default=0),
        "release_decision": release_decision,
        "decision_consistency": decision_consistency,
        "summary_marker_audit_passed": marker_passed,
        "summary_marker_hit_count": marker_hit_count,
        "boundary_context_request_delivered": _delivery_has_allowed_file(delivery, BOUNDARY_CONTEXT_REQUEST_FILENAME),
        "summary_command": delivery.get("summary_command"),
        "follow_up": _follow_up(return_status, delivery),
    }


def _return_status(
    *,
    exists: bool,
    parse_error: str,
    schema_valid: bool,
    complete: bool,
    marker_hit_count: int,
    marker_passed: bool,
    release_decision: str,
    decision_consistency: str,
) -> str:
    if not exists:
        return "missing_summary"
    if parse_error or not schema_valid:
        return "invalid_summary"
    if marker_hit_count or not marker_passed:
        return "privacy_blocked"
    if not complete:
        return "incomplete_summary"
    if decision_consistency == "inconsistent" or release_decision == "unrecorded":
        return "needs_decision_followup"
    return "complete"


def _follow_up(return_status: str, delivery: dict[str, Any]) -> str:
    command = delivery.get("summary_command") or "make evidence-observation-summary ..."
    if return_status == "missing_summary":
        return f"Wait for the reviewer return, then run: {command}"
    if return_status == "invalid_summary":
        return f"Regenerate the sanitized reviewer_observation_summary.json with: {command}"
    if return_status == "privacy_blocked":
        return "Discard or redact the affected observation/summary before using it in external validation."
    if return_status == "incomplete_summary":
        return "Ask the reviewer to complete missing fields/questions, then regenerate the sanitized summary."
    if return_status == "needs_decision_followup":
        return "Clarify approve/review/block wording with the reviewer, then regenerate the sanitized summary."
    return "No per-review follow-up needed; include this summary in the external validation readout."


def _blockers(
    schema_check: dict[str, Any],
    distribution: dict[str, Any],
    input_audit: dict[str, Any],
    sessions: list[dict[str, Any]],
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if not schema_check["exists"]:
        blockers.append({"code": "missing_distribution_manifest", "component": "external_review_distribution", "detail": "artifact is missing"})
    elif not schema_check["schema_valid"]:
        blockers.append({"code": "invalid_distribution_schema", "component": "external_review_distribution", "detail": str(schema_check.get("schema_version"))})
    if input_audit["marker_hit_count"] or not input_audit["passed"]:
        blockers.append({"code": "privacy_marker_audit_failed", "component": "input_marker_audit", "detail": "configured sensitive-marker audit did not pass"})
    if schema_check["schema_valid"] and distribution.get("distribution_status") != "ready_to_distribute":
        blockers.append({"code": "distribution_not_ready", "component": "external_review_distribution", "detail": str(distribution.get("distribution_status"))})
    for session in sessions:
        status = session["return_status"]
        if status != "complete":
            blockers.append({"code": status, "component": str(session["session_id"]), "detail": str(session["summary_path"])})
    return blockers


def _ledger_status(schema_check: dict[str, Any], blockers: list[dict[str, str]], sessions: list[dict[str, Any]]) -> str:
    codes = {blocker["code"] for blocker in blockers}
    if "privacy_marker_audit_failed" in codes or any(session["return_status"] == "privacy_blocked" for session in sessions):
        return "privacy_blocked"
    if not schema_check["schema_valid"]:
        return "missing_required_evidence"
    if any(session["return_status"] == "missing_summary" for session in sessions):
        return "waiting_for_returns"
    if any(session["return_status"] in {"invalid_summary", "incomplete_summary", "needs_decision_followup"} for session in sessions):
        return "needs_followup"
    if sessions and all(session["return_status"] == "complete" for session in sessions):
        return "ready_for_external_validation_readout"
    return "waiting_for_returns"


def _summary(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for session in sessions:
        status = str(session["return_status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "session_count": len(sessions),
        "complete_count": counts.get("complete", 0),
        "missing_summary_count": counts.get("missing_summary", 0),
        "invalid_summary_count": counts.get("invalid_summary", 0),
        "incomplete_summary_count": counts.get("incomplete_summary", 0),
        "decision_followup_count": counts.get("needs_decision_followup", 0),
        "privacy_blocked_count": counts.get("privacy_blocked", 0),
        "return_status_counts": counts,
    }


def _review_input_coverage(deliveries: list[dict[str, Any]]) -> dict[str, Any]:
    delivered_session_ids: list[str] = []
    missing_session_ids: list[str] = []
    for index, delivery in enumerate(deliveries, start=1):
        session_id = str(delivery.get("session_id") or f"review_{index}")
        if _delivery_has_allowed_file(delivery, BOUNDARY_CONTEXT_REQUEST_FILENAME):
            delivered_session_ids.append(session_id)
        else:
            missing_session_ids.append(session_id)
    if not deliveries:
        status = "not_in_distribution_manifest"
    elif len(delivered_session_ids) == len(deliveries):
        status = "delivered_to_all_sessions"
    elif delivered_session_ids:
        status = "partially_delivered"
    else:
        status = "not_in_distribution_manifest"
    return {
        "boundary_context_request_filename": BOUNDARY_CONTEXT_REQUEST_FILENAME,
        "boundary_context_request_delivery_status": status,
        "session_count": len(deliveries),
        "delivered_session_count": len(delivered_session_ids),
        "missing_session_count": len(missing_session_ids),
        "delivered_session_ids": delivered_session_ids,
        "missing_session_ids": missing_session_ids,
        "boundary_context_request_is_execution_proof": False,
        "boundary_context_request_is_approved_context": False,
        "boundary_context_request_changes_return_status": False,
    }


def _delivery_has_allowed_file(delivery: dict[str, Any], filename: str) -> bool:
    files = delivery.get("allowed_files", []) if isinstance(delivery.get("allowed_files"), list) else []
    return any(isinstance(file_entry, dict) and str(file_entry.get("name")) == filename for file_entry in files)


def _commands(sessions: list[dict[str, Any]]) -> list[str]:
    commands: list[str] = []
    for session in sessions:
        if session["return_status"] != "complete" and session.get("summary_command"):
            commands.append(str(session["summary_command"]))
    if sessions:
        commands.extend(["make evidence-external-validation-readout", "make evidence-readiness", "make evidence-remediation-queue"])
    return _dedupe_strings(commands)


def _deliveries(distribution: dict[str, Any]) -> list[dict[str, Any]]:
    deliveries = distribution.get("deliveries", []) if isinstance(distribution.get("deliveries"), list) else []
    return [delivery for delivery in deliveries if isinstance(delivery, dict)]


def _schema_check(path: Path, payload: dict[str, Any], expected: str) -> dict[str, Any]:
    return {
        "path": _display_path(path),
        "exists": path.exists(),
        "schema_version": payload.get("schema_version"),
        "schema_valid": payload.get("schema_version") == expected,
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "missing", "load_error": "missing_file"}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": "invalid_json", "load_error": "invalid_json"}
    return loaded if isinstance(loaded, dict) else {"schema_version": "invalid_shape", "load_error": "json_not_object"}


def _safe_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "checked_files": audit.get("checked_files", []),
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(audit.get("markers_checked", [])) or audit.get("marker_count", 0),
        "marker_hit_count": audit.get("marker_hit_count", 0),
        "passed": audit.get("passed", False),
        "hit_files": sorted({str(hit.get("file")) for hit in audit.get("hits", []) if isinstance(hit, dict)}) or audit.get("hit_files", []),
    }


def _decision_label(value: Any) -> str:
    label = str(value or "unrecorded")
    return label if label in {"approve", "review", "block", "unsure", "unrecorded"} else "unrecorded"


def _resolve_path(value: Any) -> Path:
    path = Path(str(value or ""))
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    deduped: list[Path] = []
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _markdown(payload: dict[str, Any]) -> str:
    output_audit = payload.get("output_marker_audit", {"passed": "pending", "marker_hit_count": "pending"})
    summary = payload["summary"]
    lines = [
        "# External Review Return Ledger",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Ledger status: `{payload['ledger_status']}`",
        f"- Distribution status: `{payload.get('distribution_status')}`",
        f"- Target review count: `{payload.get('target_review_count')}`",
        f"- Complete returns: `{summary['complete_count']}/{summary['session_count']}`",
        f"- Missing summaries: `{summary['missing_summary_count']}`",
        f"- Incomplete summaries: `{summary['incomplete_summary_count']}`",
        f"- Decision follow-up needed: `{summary['decision_followup_count']}`",
        f"- Privacy-blocked summaries: `{summary['privacy_blocked_count']}`",
        f"- Boundary context request delivery: `{payload['review_input_coverage']['boundary_context_request_delivery_status']}` (`{payload['review_input_coverage']['delivered_session_count']}/{payload['review_input_coverage']['session_count']}` sessions)",
        "",
        "## Reviewer input coverage",
        "",
        f"- Boundary context request file: `{payload['review_input_coverage']['boundary_context_request_filename']}`",
        f"- Delivery status: `{payload['review_input_coverage']['boundary_context_request_delivery_status']}`",
        f"- Delivered sessions: `{','.join(payload['review_input_coverage']['delivered_session_ids']) if payload['review_input_coverage']['delivered_session_ids'] else 'none'}`",
        f"- Missing sessions: `{','.join(payload['review_input_coverage']['missing_session_ids']) if payload['review_input_coverage']['missing_session_ids'] else 'none'}`",
        "- Boundary context request is approved context: `False`",
        "- Boundary context request is execution proof: `False`",
        "- Boundary context request changes return status: `False`",
        "",
        "## Per-reviewer returns",
        "",
        "| Reviewer slot | Return status | Summary exists | Complete | Decision | Context request delivered | Follow-up |",
        "|---|---|---:|---:|---|---:|---|",
    ]
    for session in payload["sessions"]:
        lines.append(
            f"| `{session['session_id']}` | `{session['return_status']}` | `{session['summary_exists']}` | `{session['complete']}` | `{session['release_decision']}` | `{session['boundary_context_request_delivered']}` | {session['follow_up']} |"
        )
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}` on `{blocker['component']}`: {blocker['detail']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Commands", ""])
    if payload["commands"]:
        lines.extend(f"- `{command}`" for command in payload["commands"])
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Marker audit",
        "",
        f"- Input marker audit passed: `{payload['input_marker_audit']['passed']}`",
        f"- Input marker hits: `{payload['input_marker_audit']['marker_hit_count']}`",
        f"- Output marker audit passed: `{output_audit['passed']}`",
        f"- Output marker hits: `{output_audit['marker_hit_count']}`",
        "",
        "## Non-claims",
        "",
    ])
    lines.extend(f"- {claim}" for claim in payload["non_claims"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized external review return/follow-up ledger.")
    parser.add_argument("--distribution-manifest", default=str(DEFAULT_DISTRIBUTION))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if configured sensitive markers are present (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write the ledger even when configured sensitive markers are present")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()
    payload = build_external_review_return_ledger(
        distribution_manifest=args.distribution_manifest,
        output_dir=args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"external review return ledger -> {Path(args.output_dir) / 'external_review_return_ledger.md'}")
    print(json.dumps({
        "ledger_status": payload["ledger_status"],
        "complete_count": payload["summary"]["complete_count"],
        "session_count": payload["summary"]["session_count"],
        "blocker_count": len(payload["blockers"]),
    }, indent=2))


if __name__ == "__main__":
    main()

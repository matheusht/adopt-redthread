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

SCHEMA_VERSION = "adopt_redthread.external_review_distribution_manifest.v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "external_review_distribution"
DEFAULT_HANDOFF_MANIFEST = REPO_ROOT / "runs" / "external_review_handoff" / "external_review_handoff_manifest.json"
DEFAULT_SESSION_BATCH = REPO_ROOT / "runs" / "external_review_sessions" / "external_review_session_batch.json"
DEFAULT_FRESHNESS_MANIFEST = REPO_ROOT / "runs" / "evidence_freshness" / "evidence_freshness_manifest.json"

EXPECTED_SCHEMAS = {
    "handoff": "adopt_redthread.external_review_handoff.v1",
    "session_batch": "adopt_redthread.external_review_session_batch.v1",
    "freshness": "adopt_redthread.evidence_freshness_manifest.v1",
}


def build_external_review_distribution_manifest(
    *,
    handoff_manifest: str | Path = DEFAULT_HANDOFF_MANIFEST,
    session_batch: str | Path = DEFAULT_SESSION_BATCH,
    freshness_manifest: str | Path = DEFAULT_FRESHNESS_MANIFEST,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Build a sanitized distribution manifest for external reviewer sessions.

    This is packaging control-plane evidence only. It tells an operator which
    already-generated session folders may be sent to reviewers and which summary
    paths are expected back. It does not read raw captures, source files,
    credentials, request/response bodies, write-context values, or raw reviewer
    answers, and it is not validation evidence by itself.
    """

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    handoff_path = Path(handoff_manifest)
    batch_path = Path(session_batch)
    freshness_path = Path(freshness_manifest)

    handoff = _load_json(handoff_path)
    batch = _load_json(batch_path)
    freshness = _load_json(freshness_path)

    input_paths = [path for path in (handoff_path, batch_path, freshness_path) if path.exists()]
    input_paths.extend(_session_artifact_paths(batch))
    input_audit = _safe_audit(audit_sanitized_markdown(_dedupe_paths(input_paths)))
    if fail_on_marker_hit and input_audit["marker_hit_count"]:
        raise RuntimeError(f"external review distribution marker audit failed with {input_audit['marker_hit_count']} hits")

    schema_checks = {
        "handoff": _schema_check(handoff_path, handoff, EXPECTED_SCHEMAS["handoff"]),
        "session_batch": _schema_check(batch_path, batch, EXPECTED_SCHEMAS["session_batch"]),
        "freshness": _schema_check(freshness_path, freshness, EXPECTED_SCHEMAS["freshness"]),
    }
    deliveries = _deliveries(batch)
    blockers = _blockers(schema_checks, handoff, batch, freshness, input_audit, deliveries)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "distribution_status": _distribution_status(blockers),
        "artifact_policy": "Distribution entries point only to isolated external review session folders containing sanitized artifacts and blank observation templates. Do not add raw captures, credentials, request/response bodies, source files, write-context values, or prior reviewer answers.",
        "schema_checks": schema_checks,
        "handoff_status": handoff.get("handoff_status"),
        "session_status": batch.get("session_status"),
        "freshness_status": freshness.get("freshness_status"),
        "validation_status": batch.get("validation_status") or handoff.get("validation_status"),
        "target_review_count": batch.get("target_review_count") or handoff.get("target_review_count"),
        "deliveries": deliveries,
        "blockers": blockers,
        "input_marker_audit": input_audit,
        "operator_instructions": _operator_instructions(deliveries),
        "non_claims": [
            "A distribution manifest is not external validation.",
            "A ready-to-distribute session is not a completed review.",
            "This manifest does not include or summarize raw reviewer answers.",
            "This manifest does not prove buyer demand, production readiness, boundary execution, or whole-app safety.",
            "This manifest does not change local bridge approve/review/block verdict semantics.",
        ],
    }
    json_path = output_root / "external_review_distribution_manifest.json"
    md_path = output_root / "external_review_distribution_manifest.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")

    output_audit = _safe_audit(audit_sanitized_markdown([json_path, md_path]))
    if fail_on_marker_hit and output_audit["marker_hit_count"]:
        raise RuntimeError(f"external review distribution output marker audit failed with {output_audit['marker_hit_count']} hits")
    payload["output_marker_audit"] = output_audit
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _deliveries(batch: dict[str, Any]) -> list[dict[str, Any]]:
    sessions = batch.get("sessions", []) if isinstance(batch.get("sessions"), list) else []
    deliveries: list[dict[str, Any]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        allowed = session.get("allowed_artifacts", {}) if isinstance(session.get("allowed_artifacts"), dict) else {}
        files = []
        for name, entry in sorted(allowed.items()):
            if not isinstance(entry, dict):
                continue
            files.append({
                "name": str(name),
                "path": entry.get("path"),
                "sha256": entry.get("sha256"),
                "byte_count": entry.get("byte_count"),
                "line_count": entry.get("line_count"),
            })
        deliveries.append({
            "session_id": str(session.get("session_id", "unknown_session")),
            "session_dir": session.get("session_dir"),
            "artifact_dir": session.get("artifact_dir"),
            "allowed_file_count": len(files),
            "allowed_files": files,
            "filled_observation_path": session.get("filled_observation_path"),
            "expected_summary_path": session.get("expected_summary_path"),
            "summary_command": session.get("summary_command"),
            "distribution_rule": "send exactly this session folder to exactly one reviewer; do not mix reviewer folders or include prior reviewer answers",
        })
    return deliveries


def _blockers(
    schema_checks: dict[str, dict[str, Any]],
    handoff: dict[str, Any],
    batch: dict[str, Any],
    freshness: dict[str, Any],
    input_audit: dict[str, Any],
    deliveries: list[dict[str, Any]],
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for label, check in schema_checks.items():
        if not check["exists"]:
            blockers.append({"code": "missing_required_evidence", "component": label, "detail": "artifact is missing"})
        elif not check["schema_valid"]:
            blockers.append({"code": "invalid_required_evidence_schema", "component": label, "detail": str(check.get("schema_version"))})
    if input_audit["marker_hit_count"] or not input_audit["passed"]:
        blockers.append({"code": "privacy_marker_audit_failed", "component": "input_marker_audit", "detail": "configured sensitive-marker audit did not pass"})
    if schema_checks["handoff"]["schema_valid"] and handoff.get("handoff_status") != "ready_for_external_cold_review":
        blockers.append({"code": "handoff_not_ready", "component": "external_review_handoff", "detail": str(handoff.get("handoff_status"))})
    if schema_checks["session_batch"]["schema_valid"] and batch.get("session_status") != "ready_for_external_reviewer_distribution":
        blockers.append({"code": "session_batch_not_ready", "component": "external_review_session_batch", "detail": str(batch.get("session_status"))})
    if schema_checks["freshness"]["schema_valid"] and freshness.get("freshness_status") != "fresh":
        blockers.append({"code": "stale_or_missing_evidence", "component": "evidence_freshness", "detail": str(freshness.get("freshness_status"))})
    target = _safe_int(batch.get("target_review_count") or handoff.get("target_review_count"), default=0)
    if target and len(deliveries) < target:
        blockers.append({"code": "insufficient_review_sessions", "component": "external_review_session_batch", "detail": f"{len(deliveries)}/{target}"})
    if not deliveries and schema_checks["session_batch"]["schema_valid"]:
        blockers.append({"code": "missing_review_sessions", "component": "external_review_session_batch", "detail": "no sessions listed"})
    return blockers


def _distribution_status(blockers: list[dict[str, str]]) -> str:
    codes = {blocker["code"] for blocker in blockers}
    if "privacy_marker_audit_failed" in codes:
        return "privacy_blocked"
    if "missing_required_evidence" in codes or "invalid_required_evidence_schema" in codes:
        return "missing_required_evidence"
    if "stale_or_missing_evidence" in codes:
        return "stale_or_missing_evidence"
    if codes:
        return "not_ready_to_distribute"
    return "ready_to_distribute"


def _operator_instructions(deliveries: list[dict[str, Any]]) -> list[str]:
    instructions = [
        "Run make evidence-freshness immediately before distribution and distribute only if this manifest remains ready_to_distribute.",
        "Send each reviewer exactly one review_N folder from runs/external_review_sessions and no repo access or raw run material.",
        "Require reviewers to fill only their own filled_reviewer_observation.md before any walkthrough.",
        "Summarize each returned observation with its recorded summary_command and then rebuild the external validation readout.",
    ]
    if deliveries:
        instructions.append(f"Expected completed summaries: {', '.join(str(d['expected_summary_path']) for d in deliveries)}.")
    return instructions


def _session_artifact_paths(batch: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for delivery in _deliveries(batch):
        for file_entry in delivery["allowed_files"]:
            raw_path = file_entry.get("path")
            if raw_path:
                paths.append(REPO_ROOT / str(raw_path) if not Path(str(raw_path)).is_absolute() else Path(str(raw_path)))
        for key in ("filled_observation_path",):
            raw_path = delivery.get(key)
            if raw_path:
                paths.append(REPO_ROOT / str(raw_path) if not Path(str(raw_path)).is_absolute() else Path(str(raw_path)))
    return [path for path in paths if path.exists()]


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


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    deduped: list[Path] = []
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _markdown(payload: dict[str, Any]) -> str:
    output_audit = payload.get("output_marker_audit", {"passed": "pending", "marker_hit_count": "pending"})
    lines = [
        "# External Review Distribution Manifest",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Distribution status: `{payload['distribution_status']}`",
        f"- Handoff status: `{payload.get('handoff_status')}`",
        f"- Session status: `{payload.get('session_status')}`",
        f"- Freshness status: `{payload.get('freshness_status')}`",
        f"- Validation status: `{payload.get('validation_status')}`",
        f"- Target review count: `{payload.get('target_review_count')}`",
        f"- Delivery count: `{len(payload['deliveries'])}`",
        "",
        "## Deliveries",
        "",
        "| Reviewer slot | Session folder | Allowed files | Filled observation | Expected summary |",
        "|---|---|---:|---|---|",
    ]
    for delivery in payload["deliveries"]:
        lines.append(
            f"| `{delivery['session_id']}` | `{delivery.get('session_dir')}` | `{delivery['allowed_file_count']}` | `{delivery.get('filled_observation_path')}` | `{delivery.get('expected_summary_path')}` |"
        )
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}` on `{blocker['component']}`: {blocker['detail']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Operator instructions", ""])
    lines.extend(f"- {instruction}" for instruction in payload["operator_instructions"])
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


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized external review distribution manifest.")
    parser.add_argument("--handoff-manifest", default=str(DEFAULT_HANDOFF_MANIFEST))
    parser.add_argument("--session-batch", default=str(DEFAULT_SESSION_BATCH))
    parser.add_argument("--freshness-manifest", default=str(DEFAULT_FRESHNESS_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if configured sensitive markers are present (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write the manifest even when configured sensitive markers are present")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()
    payload = build_external_review_distribution_manifest(
        handoff_manifest=args.handoff_manifest,
        session_batch=args.session_batch,
        freshness_manifest=args.freshness_manifest,
        output_dir=args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"external review distribution manifest -> {Path(args.output_dir) / 'external_review_distribution_manifest.md'}")
    print(json.dumps({
        "distribution_status": payload["distribution_status"],
        "delivery_count": len(payload["deliveries"]),
        "blocker_count": len(payload["blockers"]),
    }, indent=2))


if __name__ == "__main__":
    main()

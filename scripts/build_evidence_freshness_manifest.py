from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_reviewer_packet import audit_sanitized_markdown

SCHEMA_VERSION = "adopt_redthread.evidence_freshness_manifest.v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "evidence_freshness"
DEFAULT_REVIEWER_PACKET = REPO_ROOT / "runs" / "reviewer_packet" / "reviewer_packet.json"
DEFAULT_HANDOFF_MANIFEST = REPO_ROOT / "runs" / "external_review_handoff" / "external_review_handoff_manifest.json"
DEFAULT_SESSION_BATCH = REPO_ROOT / "runs" / "external_review_sessions" / "external_review_session_batch.json"

DEFAULT_SOURCE_ARTIFACTS = {
    "evidence_report": REPO_ROOT / "runs" / "reviewed_write_reference" / "evidence_report.md",
    "evidence_matrix": REPO_ROOT / "runs" / "evidence_matrix" / "evidence_matrix.md",
    "reviewer_packet": REPO_ROOT / "runs" / "reviewer_packet" / "reviewer_packet.md",
    "reviewer_observation_template": REPO_ROOT / "runs" / "reviewer_packet" / "reviewer_observation_template.md",
    "boundary_probe_result": REPO_ROOT / "runs" / "boundary_probe_result" / "tenant_user_boundary_probe_result.md",
}


def build_evidence_freshness_manifest(
    *,
    reviewer_packet: str | Path = DEFAULT_REVIEWER_PACKET,
    handoff_manifest: str | Path = DEFAULT_HANDOFF_MANIFEST,
    session_batch: str | Path = DEFAULT_SESSION_BATCH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    source_artifacts: dict[str, str | Path] | None = None,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Build a sanitized hash/freshness manifest for reviewer evidence copies.

    The manifest checks only known reviewer-facing artifacts and their generated
    manifests. It does not inspect raw HAR files, auth/session material, request or
    response bodies, source files, or staging write-context values.
    """

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    packet_path = Path(reviewer_packet)
    handoff_path = Path(handoff_manifest)
    batch_path = Path(session_batch)
    sources = {key: Path(value) for key, value in (source_artifacts or DEFAULT_SOURCE_ARTIFACTS).items()}

    packet = _load_json(packet_path)
    handoff = _load_json(handoff_path)
    batch = _load_json(batch_path)

    source_records = {label: _artifact_record(path) for label, path in sources.items()}
    checks: list[dict[str, Any]] = []
    checks.extend(_packet_checks(packet, source_records))
    checks.extend(_handoff_checks(handoff, source_records))
    checks.extend(_session_checks(batch, handoff))

    audit_paths = _existing_paths([packet_path, handoff_path, batch_path])
    audit_paths.extend(Path(record["path"]) for record in source_records.values() if record.get("exists"))
    audit_paths.extend(Path(check["copy_path"]) for check in checks if check.get("copy_exists"))
    raw_marker_audit = audit_sanitized_markdown(_dedupe_paths(audit_paths))
    if fail_on_marker_hit and raw_marker_audit.get("marker_hit_count", 0):
        raise RuntimeError(f"freshness marker audit failed with {raw_marker_audit['marker_hit_count']} hits")
    marker_audit = _safe_marker_audit(raw_marker_audit)

    summary = _summary(checks)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "freshness_status": _freshness_status(summary, marker_audit),
        "artifact_policy": "Freshness checks compare hashes for known sanitized reviewer-facing artifacts only. They do not read raw captures, session material, credential values, request/response bodies, source code, or write-context values.",
        "source_artifacts": source_records,
        "manifests": {
            "reviewer_packet": _artifact_record(packet_path),
            "external_review_handoff": _artifact_record(handoff_path),
            "external_review_session_batch": _artifact_record(batch_path),
        },
        "copy_checks": checks,
        "summary": summary,
        "sanitized_marker_audit": marker_audit,
        "non_claims": [
            "Fresh hashes do not prove external validation.",
            "Fresh hashes do not prove production readiness or whole-app safety.",
            "Fresh hashes do not change local bridge approve/review/block verdict semantics.",
        ],
    }
    (output_root / "evidence_freshness_manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output_root / "evidence_freshness_manifest.md").write_text(_markdown(payload), encoding="utf-8")
    return payload


def _packet_checks(packet: dict[str, Any], sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    manifest = packet.get("artifact_manifest", {}) if isinstance(packet.get("artifact_manifest"), dict) else {}
    checks = []
    for label, entry in manifest.items():
        if label == "boundary_probe_result":
            source_label = "boundary_probe_result"
        else:
            source_label = str(label)
        if source_label not in sources:
            continue
        checks.append(_check_copy(
            stage="reviewer_packet_manifest",
            artifact_label=source_label,
            source=sources[source_label],
            copy_path=Path(str(entry.get("path", ""))),
            manifest_sha=entry.get("sha256"),
        ))
    return checks


def _handoff_checks(handoff: dict[str, Any], sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts = handoff.get("artifacts", {}) if isinstance(handoff.get("artifacts"), dict) else {}
    checks = []
    for label, entry in artifacts.items():
        source_label = "boundary_probe_result" if label == "boundary_probe_result" else str(label)
        if source_label not in sources:
            continue
        checks.append(_check_copy(
            stage="external_review_handoff",
            artifact_label=source_label,
            source=sources[source_label],
            copy_path=Path(str(entry.get("path", ""))),
            manifest_sha=entry.get("sha256"),
        ))
    return checks


def _session_checks(batch: dict[str, Any], handoff: dict[str, Any]) -> list[dict[str, Any]]:
    handoff_by_filename = {
        Path(str(entry.get("path", ""))).name: _entry_record(entry)
        for entry in (handoff.get("artifacts", {}) if isinstance(handoff.get("artifacts"), dict) else {}).values()
        if isinstance(entry, dict) and entry.get("path")
    }
    checks = []
    sessions = batch.get("sessions", []) if isinstance(batch.get("sessions"), list) else []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        session_id = str(session.get("session_id", "unknown_session"))
        allowed = session.get("allowed_artifacts", {}) if isinstance(session.get("allowed_artifacts"), dict) else {}
        for filename, entry in allowed.items():
            if not isinstance(entry, dict):
                continue
            source = handoff_by_filename.get(str(filename), {"path": None, "exists": False, "sha256": None})
            checks.append(_check_copy(
                stage=f"external_review_session:{session_id}",
                artifact_label=str(filename),
                source=source,
                copy_path=Path(str(entry.get("path", ""))),
                manifest_sha=entry.get("sha256"),
            ))
    return checks


def _check_copy(*, stage: str, artifact_label: str, source: dict[str, Any], copy_path: Path, manifest_sha: Any) -> dict[str, Any]:
    actual = _artifact_record(copy_path)
    expected_sha = source.get("sha256")
    manifest_sha_text = str(manifest_sha) if manifest_sha else None
    status = "fresh"
    reasons: list[str] = []
    if not source.get("exists"):
        status = "missing_source"
        reasons.append("source_missing")
    if not actual.get("exists"):
        status = "missing_copy"
        reasons.append("copy_missing")
    if not manifest_sha_text:
        status = "missing_manifest_sha"
        reasons.append("manifest_sha_missing")
    if actual.get("exists") and manifest_sha_text and actual.get("sha256") != manifest_sha_text:
        status = "stale_or_tampered_copy"
        reasons.append("copy_hash_differs_from_manifest")
    if actual.get("exists") and expected_sha and actual.get("sha256") != expected_sha:
        status = "stale_against_source"
        reasons.append("copy_hash_differs_from_source")
    if manifest_sha_text and expected_sha and manifest_sha_text != expected_sha:
        status = "manifest_stale_against_source"
        reasons.append("manifest_hash_differs_from_source")
    return {
        "stage": stage,
        "artifact_label": artifact_label,
        "source_path": source.get("path"),
        "copy_path": _display_path(copy_path),
        "expected_source_sha256": expected_sha,
        "manifest_sha256": manifest_sha_text,
        "actual_copy_sha256": actual.get("sha256"),
        "copy_exists": actual.get("exists", False),
        "status": status,
        "reasons": reasons,
    }


def _entry_record(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": entry.get("path"),
        "exists": bool(entry.get("path")),
        "sha256": entry.get("sha256"),
        "byte_count": entry.get("byte_count"),
        "line_count": entry.get("line_count"),
    }


def _artifact_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": _display_path(path), "exists": False, "sha256": None, "byte_count": 0, "line_count": 0}
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    return {
        "path": _display_path(path),
        "exists": True,
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_count": len(data),
        "line_count": len(text.splitlines()),
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "missing", "load_error": "missing_file", "path": _display_path(path)}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": "invalid_json", "load_error": "invalid_json", "path": _display_path(path)}
    return loaded if isinstance(loaded, dict) else {"schema_version": "invalid_shape", "load_error": "json_not_object", "path": _display_path(path)}


def _safe_marker_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "checked_files": audit.get("checked_files", []),
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(audit.get("markers_checked", [])),
        "marker_hit_count": audit.get("marker_hit_count", 0),
        "passed": audit.get("passed", False),
        "hit_files": sorted({str(hit.get("file")) for hit in audit.get("hits", []) if isinstance(hit, dict)}),
    }


def _summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    fresh = sum(1 for check in checks if check["status"] == "fresh")
    stale = sum(1 for check in checks if check["status"] not in {"fresh", "missing_copy", "missing_source"})
    missing = sum(1 for check in checks if check["status"] in {"missing_copy", "missing_source"})
    return {
        "copy_check_count": len(checks),
        "fresh_count": fresh,
        "stale_count": stale,
        "missing_count": missing,
        "problem_count": len(checks) - fresh,
        "problem_artifacts": [
            {"stage": check["stage"], "artifact_label": check["artifact_label"], "status": check["status"]}
            for check in checks
            if check["status"] != "fresh"
        ],
    }


def _freshness_status(summary: dict[str, Any], marker_audit: dict[str, Any]) -> str:
    if not marker_audit.get("passed", False):
        return "privacy_blocked"
    if summary.get("problem_count", 0):
        return "stale_or_missing"
    return "fresh"


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    audit = payload["sanitized_marker_audit"]
    lines = [
        "# Evidence Freshness Manifest",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Freshness status: `{payload['freshness_status']}`",
        f"- Copy checks: `{summary['copy_check_count']}`",
        f"- Fresh: `{summary['fresh_count']}`",
        f"- Problems: `{summary['problem_count']}`",
        f"- Marker audit passed: `{audit.get('passed', False)}`",
        f"- Marker hits: `{audit.get('marker_hit_count', 0)}`",
        "",
        "## Copy checks",
        "",
        "| Stage | Artifact | Status | Reasons |",
        "|---|---|---|---|",
    ]
    for check in payload["copy_checks"]:
        lines.append(f"| `{check['stage']}` | `{check['artifact_label']}` | `{check['status']}` | `{', '.join(check['reasons']) or 'none'}` |")
    lines.extend([
        "",
        "## Non-claims",
        "",
    ])
    lines.extend(f"- {claim}" for claim in payload["non_claims"])
    lines.append("")
    return "\n".join(lines)


def _display_path(path: Path) -> str | None:
    if not str(path):
        return None
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _existing_paths(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    deduped: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized freshness manifest for generated reviewer evidence copies.")
    parser.add_argument("--reviewer-packet", default=str(DEFAULT_REVIEWER_PACKET))
    parser.add_argument("--handoff-manifest", default=str(DEFAULT_HANDOFF_MANIFEST))
    parser.add_argument("--session-batch", default=str(DEFAULT_SESSION_BATCH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if configured sensitive markers are present (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write the manifest even when configured sensitive markers are present")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()
    payload = build_evidence_freshness_manifest(
        reviewer_packet=args.reviewer_packet,
        handoff_manifest=args.handoff_manifest,
        session_batch=args.session_batch,
        output_dir=args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"evidence freshness manifest -> {Path(args.output_dir) / 'evidence_freshness_manifest.md'}")
    print(json.dumps({
        "freshness_status": payload["freshness_status"],
        "copy_check_count": payload["summary"]["copy_check_count"],
        "problem_count": payload["summary"]["problem_count"],
        "marker_hits": payload["sanitized_marker_audit"].get("marker_hit_count", 0),
    }, indent=2))


if __name__ == "__main__":
    main()

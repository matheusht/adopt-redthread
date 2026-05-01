from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.summarize_reviewer_validation_rollup import summarize_reviewer_validation_rollup

DEFAULT_BATCH_MANIFEST = REPO_ROOT / "runs" / "external_review_sessions" / "external_review_session_batch.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "external_validation_readout"
SCHEMA_VERSION = "adopt_redthread.external_validation_readout.v1"
BATCH_SCHEMA = "adopt_redthread.external_review_session_batch.v1"


def build_external_validation_readout(
    *,
    batch_manifest: str | Path = DEFAULT_BATCH_MANIFEST,
    summary_paths: list[str | Path] | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Build a sanitized external validation readout from session summaries.

    This reads reviewer_observation_summary JSON files only. It does not read raw
    observations, raw run artifacts, source files, auth/session material, or request/
    response bodies. Missing summaries are reported as pending external validation;
    they are not treated as product validation.
    """

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    batch_path = Path(batch_manifest)
    batch = _load_batch(batch_path)
    summaries = [Path(path) for path in (summary_paths if summary_paths is not None else _summary_paths_from_batch(batch))]
    rollup = summarize_reviewer_validation_rollup(
        summaries,
        output_dir=output_root,
        fail_on_marker_hit=fail_on_marker_hit,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "readout_status": _readout_status(batch, rollup),
        "validation_claim": _validation_claim(rollup),
        "artifact_policy": "Readout consumes the external review session batch manifest and sanitized reviewer_observation_summary JSON files only. It does not copy raw reviewer answers or raw app/run artifacts.",
        "batch_manifest": _display_path(batch_path),
        "batch_schema_valid": batch.get("schema_version") == BATCH_SCHEMA,
        "target_review_count": batch.get("target_review_count", rollup.get("minimum_complete_review_count", 3)),
        "summary_paths": [_display_path(path) for path in summaries],
        "rollup_path": _display_path(output_root / "reviewer_validation_rollup.json"),
        "rollup_summary": rollup.get("rollup_summary", {}),
        "theme_summary": rollup.get("theme_summary", {}),
        "rollup_validation_status": rollup.get("validation_status", "unknown"),
        "sanitized_marker_audit": rollup.get("sanitized_marker_audit", {}),
        "recommended_next_actions": _recommended_next_actions(batch, rollup),
    }
    readout_json = output_root / "external_validation_readout.json"
    readout_md = output_root / "external_validation_readout.md"
    readout_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    readout_md.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _load_batch(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "missing",
            "target_review_count": 3,
            "sessions": [],
            "batch_error": "missing_batch_manifest",
        }
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "schema_version": "invalid_json",
            "target_review_count": 3,
            "sessions": [],
            "batch_error": "invalid_batch_manifest_json",
        }
    if not isinstance(loaded, dict):
        return {
            "schema_version": "invalid_shape",
            "target_review_count": 3,
            "sessions": [],
            "batch_error": "batch_manifest_not_object",
        }
    return loaded


def _summary_paths_from_batch(batch: dict[str, Any]) -> list[Path]:
    sessions = batch.get("sessions", []) if isinstance(batch.get("sessions"), list) else []
    paths = [Path(str(session.get("expected_summary_path"))) for session in sessions if isinstance(session, dict) and session.get("expected_summary_path")]
    if paths:
        return paths
    target_count = int(batch.get("target_review_count", 3) or 3)
    return [REPO_ROOT / "runs" / "external_review_sessions" / f"review_{index}" / "reviewer_observation_summary.json" for index in range(1, target_count + 1)]


def _readout_status(batch: dict[str, Any], rollup: dict[str, Any]) -> str:
    if batch.get("schema_version") != BATCH_SCHEMA:
        return "needs_valid_external_review_session_batch"
    rollup_status = str(rollup.get("validation_status", "unknown"))
    summary = rollup.get("rollup_summary", {}) if isinstance(rollup.get("rollup_summary"), dict) else {}
    if rollup_status == "privacy_blocked":
        return "privacy_blocked"
    if rollup_status == "ready_for_validation_readout":
        return "ready_for_external_validation_readout"
    if rollup_status == "needs_decision_language_followup":
        return "needs_external_decision_language_followup"
    if rollup_status == "needs_more_complete_reviews":
        return "needs_more_complete_external_reviews"
    if rollup_status == "needs_valid_observation_summaries":
        total = int(summary.get("total_summary_count", 0) or 0)
        missing = int(summary.get("missing_or_invalid_file_count", 0) or 0)
        if total and missing == total:
            return "waiting_for_filled_external_observations"
        return "needs_valid_external_observation_summaries"
    return "unknown_external_validation_state"


def _validation_claim(rollup: dict[str, Any]) -> str:
    if rollup.get("validation_status") == "ready_for_validation_readout":
        return "external_human_validation_readout_ready_but_not_buyer_demand_or_production_readiness_proof"
    return "not_external_validation_until_required_complete_sanitized_observation_summaries_exist"


def _recommended_next_actions(batch: dict[str, Any], rollup: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if batch.get("schema_version") != BATCH_SCHEMA:
        actions.append("Rebuild the external review session batch before interpreting reviewer summaries.")
    summary = rollup.get("rollup_summary", {}) if isinstance(rollup.get("rollup_summary"), dict) else {}
    remaining = max(0, int(rollup.get("minimum_complete_review_count", 3) or 3) - int(summary.get("complete_summary_count", 0) or 0))
    if remaining:
        actions.append(f"Collect and summarize {remaining} more complete external reviewer observation(s).")
    for action in rollup.get("recommended_next_actions", []):
        action_text = str(action)
        if remaining and "more complete cold reviewer session" in action_text:
            continue
        if action_text not in actions:
            actions.append(action_text)
    if not actions:
        actions.append("Review the external validation readout with the same approve/review/block semantics; do not treat it as a whole-product safety proof.")
    return actions


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload["rollup_summary"]
    audit = payload["sanitized_marker_audit"]
    lines = [
        "# External Validation Readout",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Readout status: `{payload['readout_status']}`",
        f"- Validation claim: `{payload['validation_claim']}`",
        f"- Batch manifest: `{payload['batch_manifest']}`",
        f"- Batch schema valid: `{payload['batch_schema_valid']}`",
        f"- Rollup validation status: `{payload['rollup_validation_status']}`",
        f"- Complete summaries: `{summary.get('complete_summary_count', 0)}/{payload['target_review_count']}`",
        f"- Missing/invalid summaries: `{summary.get('missing_or_invalid_file_count', 0)}`",
        f"- Marker audit passed: `{audit.get('passed', False)}`",
        f"- Marker hits: `{audit.get('marker_hit_count', 0)}`",
        "",
        "## Summary inputs",
        "",
    ]
    lines.extend(f"- `{path}`" for path in payload["summary_paths"])
    lines.extend([
        "",
        "## Decision counts",
        "",
        f"- Decisions: `{_flat_counts(summary.get('decision_counts', {}))}`",
        f"- Behavior change recorded: `{summary.get('behavior_change_count', 0)}`",
        f"- Next probe requested: `{summary.get('next_probe_requested_count', 0)}`",
        f"- Repeat-review requested: `{summary.get('repeat_review_request_count', 0)}`",
        f"- Confusion/weak evidence recorded: `{summary.get('confusion_or_weakness_count', 0)}`",
        "",
        "## Recommended next actions",
        "",
    ])
    lines.extend(f"- {action}" for action in payload["recommended_next_actions"])
    lines.extend([
        "",
        "## Non-claims",
        "",
        "- This readout does not prove buyer demand.",
        "- This readout does not prove production readiness.",
        "- This readout does not authorize production or staging writes.",
        "- This readout does not change local bridge `approve` / `review` / `block` verdict semantics.",
        "",
    ])
    return "\n".join(lines)


def _flat_counts(counts: dict[str, Any]) -> str:
    return ",".join(f"{key}:{value}" for key, value in counts.items()) if counts else "none"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an external validation readout from sanitized review summaries.")
    parser.add_argument("--batch-manifest", default=str(DEFAULT_BATCH_MANIFEST))
    parser.add_argument("--summary", dest="summaries", action="append", help="Optional reviewer_observation_summary.json path. Repeat for multiple summaries. Defaults to the session batch expected paths.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if configured sensitive markers are present (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write the readout even when configured sensitive markers are present")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()
    payload = build_external_validation_readout(
        batch_manifest=args.batch_manifest,
        summary_paths=args.summaries,
        output_dir=args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"external validation readout -> {Path(args.output_dir) / 'external_validation_readout.md'}")
    print(json.dumps({
        "readout_status": payload["readout_status"],
        "validation_claim": payload["validation_claim"],
        "complete_summary_count": payload["rollup_summary"].get("complete_summary_count", 0),
        "marker_hits": payload["sanitized_marker_audit"].get("marker_hit_count", 0),
    }, indent=2))


if __name__ == "__main__":
    main()

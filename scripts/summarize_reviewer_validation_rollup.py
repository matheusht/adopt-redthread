from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_reviewer_packet import SENSITIVE_MARKERS

DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "reviewer_validation"
EXPECTED_SCHEMA = "adopt_redthread.reviewer_observation_summary.v1"
ROLLUP_SCHEMA = "adopt_redthread.reviewer_validation_rollup.v1"
MIN_COMPLETE_REVIEWS = 3

DECISION_LABELS = ("approve", "review", "block", "unsure", "unrecorded")
THEME_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tenant_user_boundary", ("tenant", "user", "owner", "ownership", "cross-user", "cross user", "workspace", "org", "account")),
    ("coverage_strength", ("coverage", "thin", "weak", "fixture", "dry-run", "dry run", "workflow", "replay")),
    ("confirmed_vs_replay_language", ("confirmed", "vulnerability", "finding", "auth", "context", "failure", "blocked")),
    ("write_context", ("write", "staging", "mutation", "approved context", "body")),
    ("redthread_vs_bridge_ownership", ("redthread", "bridge", "gate", "verdict", "decision owner")),
    ("artifact_navigation", ("hard to find", "where", "artifact", "packet", "matrix", "report", "navigation")),
)


def summarize_reviewer_validation_rollup(
    summary_paths: list[str | Path],
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Roll up sanitized reviewer-observation summaries into a validation signal.

    The rollup intentionally reads summary JSON files, not raw observations or run artifacts.
    Free-form reviewer answer text is used only for bounded theme counts and is not copied
    into the output.
    """

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    entries = [_load_summary(path) for path in summary_paths]
    marker_audit = _summary_marker_audit(entries)
    if fail_on_marker_hit and marker_audit["marker_hit_count"]:
        raise RuntimeError(f"reviewer validation rollup marker audit failed with {marker_audit['marker_hit_count']} hits")

    payload = {
        "schema_version": ROLLUP_SCHEMA,
        "artifact_policy": "Rollup reads reviewer_observation_summary JSON only. It does not read raw HAR/session/cookie/header/body/request/response artifacts and does not copy free-form reviewer answers.",
        "minimum_complete_review_count": MIN_COMPLETE_REVIEWS,
        "input_summaries": [_entry_public_summary(entry) for entry in entries],
        "rollup_summary": _rollup_summary(entries),
        "theme_summary": _theme_summary(entries),
        "sanitized_marker_audit": marker_audit,
    }
    payload["validation_status"] = _validation_status(payload)
    payload["recommended_next_actions"] = _recommended_next_actions(payload)

    (output_root / "reviewer_validation_rollup.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output_root / "reviewer_validation_rollup.md").write_text(_markdown(payload), encoding="utf-8")
    return payload


def _load_summary(path_like: str | Path) -> dict[str, Any]:
    path = Path(path_like)
    raw_text = path.read_text(encoding="utf-8") if path.exists() else ""
    payload: dict[str, Any] = {}
    parse_error = ""
    if raw_text:
        try:
            loaded = json.loads(raw_text)
            if isinstance(loaded, dict):
                payload = loaded
            else:
                parse_error = "summary_json_not_object"
        except json.JSONDecodeError:
            parse_error = "invalid_json"
    elif path.exists():
        parse_error = "empty_file"
    else:
        parse_error = "missing_file"
    return {
        "path": path,
        "exists": path.exists(),
        "raw_text": raw_text,
        "payload": payload,
        "parse_error": parse_error,
    }


def _entry_public_summary(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry["payload"]
    completion = payload.get("completion_summary", {}) if isinstance(payload, dict) else {}
    signals = payload.get("validation_signals", {}) if isinstance(payload, dict) else {}
    audit = payload.get("sanitized_marker_audit", {}) if isinstance(payload, dict) else {}
    schema = payload.get("schema_version", "missing") if isinstance(payload, dict) else "missing"
    return {
        "path": _display_path(entry["path"]),
        "exists": entry["exists"],
        "schema_version": schema,
        "schema_valid": schema == EXPECTED_SCHEMA,
        "parse_error": entry["parse_error"],
        "complete": bool(completion.get("complete", False)),
        "observation_status": completion.get("observation_status", "unknown"),
        "release_decision": _decision_label(signals.get("release_decision", "unrecorded")),
        "decision_consistency": signals.get("decision_consistency", "unknown"),
        "marker_audit_passed": bool(audit.get("passed", False)),
    }


def _rollup_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    public_entries = [_entry_public_summary(entry) for entry in entries]
    decision_counts = {label: 0 for label in DECISION_LABELS}
    complete_count = 0
    incomplete_count = 0
    invalid_schema_count = 0
    missing_or_invalid_count = 0
    marker_failed_count = 0
    decision_inconsistent_count = 0
    behavior_change_count = 0
    next_probe_count = 0
    repeat_review_count = 0
    confusion_count = 0

    for entry, public in zip(entries, public_entries):
        payload = entry["payload"]
        signals = payload.get("validation_signals", {}) if isinstance(payload, dict) else {}
        confusion = payload.get("confusion_summary", {}) if isinstance(payload, dict) else {}
        decision_counts[public["release_decision"]] += 1
        if public["complete"]:
            complete_count += 1
        else:
            incomplete_count += 1
        if not public["schema_valid"]:
            invalid_schema_count += 1
        if public["parse_error"]:
            missing_or_invalid_count += 1
        if public["schema_valid"] and not public["marker_audit_passed"]:
            marker_failed_count += 1
        if public["decision_consistency"] == "inconsistent":
            decision_inconsistent_count += 1
        if bool(signals.get("behavior_change_recorded", False)):
            behavior_change_count += 1
        if bool(signals.get("next_probe_requested", False)):
            next_probe_count += 1
        if bool(signals.get("wants_repeat_review", False)):
            repeat_review_count += 1
        if bool(confusion.get("has_confusion_or_weakness", False)):
            confusion_count += 1

    return {
        "total_summary_count": len(entries),
        "complete_summary_count": complete_count,
        "incomplete_summary_count": incomplete_count,
        "invalid_schema_count": invalid_schema_count,
        "missing_or_invalid_file_count": missing_or_invalid_count,
        "marker_failed_summary_count": marker_failed_count,
        "decision_inconsistent_count": decision_inconsistent_count,
        "decision_counts": decision_counts,
        "behavior_change_count": behavior_change_count,
        "next_probe_requested_count": next_probe_count,
        "repeat_review_request_count": repeat_review_count,
        "confusion_or_weakness_count": confusion_count,
    }


def _theme_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {theme: 0 for theme, _ in THEME_RULES}
    no_theme_count = 0
    for entry in entries:
        payload = entry["payload"]
        if not isinstance(payload, dict):
            no_theme_count += 1
            continue
        confusion = payload.get("confusion_summary", {})
        text = " ".join(
            str(confusion.get(key, ""))
            for key in ("unclear_or_weak_evidence", "next_probe_requested")
        ).casefold()
        matched = False
        for theme, needles in THEME_RULES:
            if any(needle in text for needle in needles):
                counts[theme] += 1
                matched = True
        if not matched:
            no_theme_count += 1
    return {
        "theme_counts": counts,
        "no_detected_theme_count": no_theme_count,
        "theme_policy": "Theme counts are keyword buckets from reviewer summaries; raw reviewer answer text is not copied into this rollup.",
    }


def _validation_status(payload: dict[str, Any]) -> str:
    summary = payload["rollup_summary"]
    if payload["sanitized_marker_audit"]["marker_hit_count"] or summary["marker_failed_summary_count"]:
        return "privacy_blocked"
    if summary["missing_or_invalid_file_count"] or summary["invalid_schema_count"]:
        return "needs_valid_observation_summaries"
    if summary["complete_summary_count"] < payload["minimum_complete_review_count"]:
        return "needs_more_complete_reviews"
    if summary["decision_inconsistent_count"]:
        return "needs_decision_language_followup"
    return "ready_for_validation_readout"


def _recommended_next_actions(payload: dict[str, Any]) -> list[str]:
    summary = payload["rollup_summary"]
    themes = payload["theme_summary"]["theme_counts"]
    actions: list[str] = []
    if payload["validation_status"] == "privacy_blocked":
        actions.append("Discard or redact affected observation summaries before using this rollup as validation evidence.")
    if summary["missing_or_invalid_file_count"] or summary["invalid_schema_count"]:
        actions.append("Regenerate missing or invalid reviewer-observation summaries before comparing reviewer behavior.")
    remaining = max(0, payload["minimum_complete_review_count"] - summary["complete_summary_count"])
    if remaining:
        actions.append(f"Run {remaining} more complete cold reviewer session(s) before treating this as a validation readout.")
    if summary["decision_inconsistent_count"]:
        actions.append("Repeat inconsistent reviews or clarify approve/review/block vocabulary before changing product wording.")
    if themes["tenant_user_boundary"]:
        actions.append("Prioritize tenant/user boundary evidence and wording in the next report or rerun trigger.")
    if themes["coverage_strength"]:
        actions.append("Make coverage strength and replay depth easier to compare in the report and matrix.")
    if themes["confirmed_vs_replay_language"]:
        actions.append("Harden language that separates confirmed findings from auth/replay/context failures.")
    if themes["write_context"]:
        actions.append("Keep write execution gated on approved non-production context and explain that gate plainly.")
    if summary["next_probe_requested_count"]:
        actions.append("Turn repeated reviewer-requested probes into explicit rerun triggers before adding new integrations.")
    if not summary["repeat_review_request_count"] and summary["complete_summary_count"]:
        actions.append("Ask whether reviewers would want this packet before every release; demand signal is still weak without it.")
    if not actions:
        actions.append("No immediate follow-up detected beyond running the next scheduled cold review.")
    return actions


def _summary_marker_audit(entries: list[dict[str, Any]]) -> dict[str, Any]:
    hit_files: set[str] = set()
    checked_files: list[str] = []
    for entry in entries:
        checked_files.append(_display_path(entry["path"]))
        lowered = entry["raw_text"].casefold()
        if any(marker.casefold() in lowered for marker in SENSITIVE_MARKERS):
            hit_files.add(_display_path(entry["path"]))
    return {
        "checked_files": checked_files,
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(SENSITIVE_MARKERS),
        "marker_hit_count": len(hit_files),
        "passed": len(hit_files) == 0,
        "hit_files": sorted(hit_files),
    }


def _decision_label(value: Any) -> str:
    label = str(value or "unrecorded")
    return label if label in DECISION_LABELS else "unrecorded"


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload["rollup_summary"]
    themes = payload["theme_summary"]
    audit = payload["sanitized_marker_audit"]
    lines = [
        "# Reviewer Validation Rollup",
        "",
        payload["artifact_policy"],
        "",
        "## Validation status",
        "",
        f"- Status: `{payload['validation_status']}`",
        f"- Complete summaries: `{summary['complete_summary_count']}/{payload['minimum_complete_review_count']}` minimum (`{summary['total_summary_count']}` provided)",
        f"- Marker audit passed: `{audit['passed']}`",
        f"- Missing/invalid files: `{summary['missing_or_invalid_file_count']}`",
        f"- Invalid schemas: `{summary['invalid_schema_count']}`",
        "",
        "## Input summaries",
        "",
        "| Summary | Exists | Schema valid | Complete | Decision | Decision consistency | Marker audit |",
        "|---|---:|---:|---:|---|---|---:|",
    ]
    for entry in payload["input_summaries"]:
        lines.append(
            "| `{path}` | `{exists}` | `{schema_valid}` | `{complete}` | `{release_decision}` | `{decision_consistency}` | `{marker_audit_passed}` |".format(**entry)
        )
    lines.extend([
        "",
        "## Decision and behavior counts",
        "",
        f"- Decisions: `{_flat_counts(summary['decision_counts'])}`",
        f"- Behavior change recorded: `{summary['behavior_change_count']}`",
        f"- Next probe requested: `{summary['next_probe_requested_count']}`",
        f"- Repeat-review requested: `{summary['repeat_review_request_count']}`",
        f"- Confusion/weak evidence recorded: `{summary['confusion_or_weakness_count']}`",
        f"- Decision inconsistencies: `{summary['decision_inconsistent_count']}`",
        "",
        "## Theme counts",
        "",
        themes["theme_policy"],
        "",
    ])
    for theme, count in themes["theme_counts"].items():
        lines.append(f"- {theme}: `{count}`")
    lines.extend([
        f"- no_detected_theme: `{themes['no_detected_theme_count']}`",
        "",
        "## Recommended next actions",
        "",
    ])
    lines.extend(f"- {action}" for action in payload["recommended_next_actions"])
    lines.extend([
        "",
        "## Configured sensitive marker check",
        "",
        f"- Passed: `{audit['passed']}`",
        f"- Marker hits: `{audit['marker_hit_count']}`",
        f"- Hit files: `{','.join(audit['hit_files']) if audit['hit_files'] else 'none'}`",
        f"- Marker set: `{audit['marker_set']}` (`{audit['marker_count']}` configured strings)",
        "",
    ])
    return "\n".join(lines)


def _flat_counts(counts: dict[str, int]) -> str:
    return ",".join(f"{key}:{value}" for key, value in counts.items())


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Roll up sanitized reviewer-observation summaries into validation signals.")
    parser.add_argument("summaries", nargs="+", help="reviewer_observation_summary.json files to aggregate")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if any summary contains configured sensitive markers (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write the rollup even when configured sensitive markers are present")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()

    rollup = summarize_reviewer_validation_rollup(
        [Path(path) for path in args.summaries],
        output_dir=args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"reviewer validation rollup -> {Path(args.output_dir) / 'reviewer_validation_rollup.md'}")
    print(json.dumps({
        "validation_status": rollup["validation_status"],
        "complete_summary_count": rollup["rollup_summary"]["complete_summary_count"],
        "total_summary_count": rollup["rollup_summary"]["total_summary_count"],
        "marker_hits": rollup["sanitized_marker_audit"]["marker_hit_count"],
        "marker_audit_passed": rollup["sanitized_marker_audit"]["passed"],
    }, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.zapi.loader import build_fixture_bundle as build_zapi_fixture_bundle

DEFAULT_EXPECTED = REPO_ROOT / "fixtures" / "reference_demos" / "atp_tennis_zapi_reference_expected.json"
DEFAULT_OUTPUT = REPO_ROOT / "runs" / "atp_tennis_reference_check" / "sanitized_evidence.json"


def build_sanitized_evidence(*, har_path: Path, run_dir: Path, expected_path: Path) -> dict[str, Any]:
    expected_doc = _load_json(expected_path)
    expected = expected_doc["expected"]
    summary = _load_json(run_dir / "workflow_summary.json")
    gate = _load_json(run_dir / "gate_verdict.json")
    replay = _load_json(run_dir / "redthread_replay_verdict.json")
    live = _load_json(run_dir / "live_workflow_replay.json")

    bundle = build_zapi_fixture_bundle(har_path)
    requirement_summary = summary.get("live_workflow_requirement_summary", {})
    workflow_class_counts = requirement_summary.get("workflow_class_counts", {})

    evidence = {
        "reference_id": expected_doc["reference_id"],
        "input_file_basename": har_path.name,
        "run_dir": str(run_dir),
        "ingestion": summary.get("ingestion"),
        "fixture_count_from_har": bundle.get("fixture_count", 0),
        "fixture_count_from_run": summary.get("fixture_count", 0),
        "endpoint_fingerprints": _endpoint_fingerprints(bundle),
        "workflow_count": summary.get("live_workflow_count", 0),
        "live_workflow_replay_executed": summary.get("live_workflow_replay_executed", False),
        "successful_workflow_count": live.get("successful_workflow_count", 0),
        "blocked_workflow_count": live.get("blocked_workflow_count", 0),
        "aborted_workflow_count": live.get("aborted_workflow_count", 0),
        "declared_response_binding_count": requirement_summary.get("declared_response_binding_count", 0),
        "applied_response_binding_count": requirement_summary.get("applied_response_binding_count", 0),
        "redthread_replay_passed": bool(replay.get("passed")),
        "redthread_dryrun_executed": summary.get("redthread_dryrun_executed", False),
        "gate_decision": gate.get("decision"),
        "gate_warnings": gate.get("warnings", []),
        "workflow_class_counts": workflow_class_counts,
        "result": "unchecked",
        "errors": [],
    }

    errors = _validate(evidence, expected)
    evidence["result"] = "pass" if not errors else "fail"
    evidence["errors"] = errors
    return evidence


def _endpoint_fingerprints(bundle: dict[str, Any]) -> list[str]:
    fingerprints = []
    for fixture in bundle.get("fixtures", []):
        method = str(fixture.get("method", "")).upper()
        path = _sanitize_path(str(fixture.get("path", "")))
        replay_class = str(fixture.get("replay_class", ""))
        fingerprints.append(f"{method} {path} [{replay_class}]")
    return sorted(set(fingerprints))


def _sanitize_path(path: str) -> str:
    sanitized_segments = []
    for segment in path.split("/"):
        if not segment:
            continue
        if _looks_like_identifier(segment):
            sanitized_segments.append(":id")
        else:
            sanitized_segments.append(segment)
    return "/" + "/".join(sanitized_segments)


def _looks_like_identifier(segment: str) -> bool:
    if len(segment) >= 12:
        return True
    has_digit = any(char.isdigit() for char in segment)
    has_alpha = any(char.isalpha() for char in segment)
    return has_digit and has_alpha


def _validate(evidence: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    checks = {
        "ingestion": evidence["ingestion"],
        "fixture_count": evidence["fixture_count_from_har"],
        "workflow_count": evidence["workflow_count"],
        "live_workflow_replay_executed": evidence["live_workflow_replay_executed"],
        "successful_workflow_count": evidence["successful_workflow_count"],
        "blocked_workflow_count": evidence["blocked_workflow_count"],
        "aborted_workflow_count": evidence["aborted_workflow_count"],
        "declared_response_binding_count": evidence["declared_response_binding_count"],
        "applied_response_binding_count": evidence["applied_response_binding_count"],
        "redthread_replay_passed": evidence["redthread_replay_passed"],
        "redthread_dryrun_executed": evidence["redthread_dryrun_executed"],
        "gate_decision": evidence["gate_decision"],
    }
    errors = []
    if evidence["fixture_count_from_har"] != evidence["fixture_count_from_run"]:
        errors.append(
            f"fixture_count mismatch between HAR ({evidence['fixture_count_from_har']}) and run ({evidence['fixture_count_from_run']})"
        )
    for key, actual in checks.items():
        if actual != expected[key]:
            errors.append(f"{key}: expected {expected[key]!r}, got {actual!r}")
    gate_warning = expected.get("gate_warning")
    if gate_warning and gate_warning not in evidence["gate_warnings"]:
        errors.append(f"gate_warning: expected {gate_warning!r} in {evidence['gate_warnings']!r}")
    workflow_class = expected.get("workflow_class")
    if workflow_class and evidence["workflow_class_counts"].get(workflow_class) != 1:
        errors.append(f"workflow_class: expected {workflow_class!r} count 1, got {evidence['workflow_class_counts']!r}")
    return errors


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"required artifact missing: {path}")
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and write a sanitized evidence summary for the ATP Tennis ZAPI reference demo."
    )
    parser.add_argument("--har", default="demo_session_filtered.har", help="Ignored raw HAR used to verify fixture extraction")
    parser.add_argument("--run-dir", default="runs/atp_tennis_01_live_bound", help="Ignored reference run artifact directory")
    parser.add_argument("--expected", default=str(DEFAULT_EXPECTED), help="Checked-in expected non-secret evidence summary")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Sanitized evidence JSON output path")
    args = parser.parse_args()

    evidence = build_sanitized_evidence(
        har_path=Path(args.har),
        run_dir=Path(args.run_dir),
        expected_path=Path(args.expected),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    if evidence["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

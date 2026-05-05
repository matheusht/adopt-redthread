from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.bridge.workflow import DEFAULT_REDTHREAD_PYTHON, DEFAULT_REDTHREAD_SRC, run_bridge_workflow
from scripts.build_evidence_report import build_evidence_report
from scripts.build_reviewer_packet import SENSITIVE_MARKERS

FORBIDDEN_RAW_FIELD_KEYS = {
    "authorization",
    "authorization_header",
    "cookie",
    "cookies",
    "headers",
    "request",
    "request_body",
    "response",
    "response_body",
    "raw_body",
    "body",
    "url",
    "target_url",
    "tenant_id",
    "user_id",
    "resource_id",
    "selector",
    "approval_label",
}

BATCH_SCHEMA_VERSION = "adopt_redthread.har_evidence_batch.v1"
SUBJECT_SCHEMA_VERSION = "adopt_redthread.har_evidence_batch_subject.v1"


def run_har_evidence_batch(
    *,
    input_dir: str | Path | None = None,
    manifest: str | Path | None = None,
    output_dir: str | Path,
    ingestion: str = "zapi",
    limit: int | None = None,
    fail_fast: bool = False,
    fail_on_marker_hit: bool = True,
    redthread_python: str | Path = DEFAULT_REDTHREAD_PYTHON,
    redthread_src: str | Path = DEFAULT_REDTHREAD_SRC,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    subjects_root = output_root / "subjects"
    subjects_root.mkdir(parents=True, exist_ok=True)

    if limit is not None and limit < 0:
        raise ValueError("--limit must be greater than or equal to 0")
    inputs = _discover_inputs(input_dir=input_dir, manifest=manifest)
    discovered_input_count = len(inputs)
    if limit is not None:
        inputs = inputs[:limit]

    subject_summaries: list[dict[str, Any]] = []
    for index, input_path in enumerate(inputs, start=1):
        subject_id = f"subject_{index:03d}"
        subject_dir = subjects_root / subject_id
        subject_dir.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix=f"{subject_id}_bridge_work_") as work_tmp:
                work_dir = Path(work_tmp)
                run_bridge_workflow(
                    input_path,
                    ingestion=ingestion,
                    output_dir=work_dir,
                    run_dryrun=True,
                    run_live_safe_replay=False,
                    run_live_workflow_replay=False,
                    auth_context=None,
                    allow_reviewed_auth=False,
                    write_context=None,
                    allow_reviewed_writes=False,
                    redthread_python=redthread_python,
                    redthread_src=redthread_src,
                )
                try:
                    build_evidence_report(work_dir, work_dir / "evidence_report.md")
                except Exception:
                    # The batch summary is still useful when the bridge produced machine-readable output.
                    pass
                summary = build_subject_summary(subject_id, work_dir, batch_status="processed")
                _write_sanitized_subject_artifacts(work_dir, subject_dir, summary)
        except Exception as exc:
            summary = _failed_subject_summary(subject_id, exc)
            _write_json(subject_dir / "subject_summary.json", summary)
            _write_text(subject_dir / "subject_summary.md", _subject_summary_markdown(summary))
            if fail_fast:
                raise
        _write_json(subject_dir / "subject_summary.json", summary)
        _write_text(subject_dir / "subject_summary.md", _subject_summary_markdown(summary))
        audit = marker_audit(_generated_subject_artifact_text(subject_dir))
        summary["privacy_audit"] = audit
        if not audit["passed"]:
            summary = _privacy_blocked_subject_summary(subject_id, audit)
            _replace_subject_with_privacy_block(subject_dir, summary, audit)
        else:
            _write_json(subject_dir / "privacy_audit.json", audit)
            _write_json(subject_dir / "subject_summary.json", summary)
            _write_text(subject_dir / "subject_summary.md", _subject_summary_markdown(summary))
        subject_summaries.append(summary)

    artifacts = _build_batch_artifacts(
        subject_summaries,
        total_inputs=len(inputs),
        discovered_input_count=discovered_input_count,
        limit=limit,
        ingestion=ingestion,
    )
    aggregate_text = "\n".join(
        json.dumps(artifacts[name], sort_keys=True) if name.endswith("json") else artifacts[name]
        for name in artifacts
    )
    batch_audit = marker_audit(aggregate_text)
    artifacts["privacy_audit.json"] = batch_audit

    if not batch_audit["passed"]:
        minimal = {
            "schema_version": BATCH_SCHEMA_VERSION,
            "batch_status": "privacy_blocked",
            "subject_count": len(subject_summaries),
            "privacy_audit": batch_audit,
        }
        _write_json(output_root / "privacy_audit.json", batch_audit)
        _write_json(output_root / "batch_manifest.json", minimal)
        if fail_on_marker_hit:
            raise RuntimeError("HAR evidence batch privacy audit failed")
        return minimal

    for filename, payload in artifacts.items():
        path = output_root / filename
        if filename.endswith(".json"):
            _write_json(path, payload)
        else:
            _write_text(path, payload)

    if fail_on_marker_hit and any(not s.get("privacy_audit", {}).get("passed", False) for s in subject_summaries):
        raise RuntimeError("one or more HAR evidence batch subjects failed privacy audit")

    return artifacts["batch_manifest.json"]


def build_subject_summary(subject_id: str, subject_dir: str | Path, *, batch_status: str) -> dict[str, Any]:
    root = Path(subject_dir)
    workflow_summary = _load_optional(root / "workflow_summary.json") or {}
    gate = _load_optional(root / "gate_verdict.json") or {}
    redthread = _load_optional(root / "redthread_replay_verdict.json") or {}
    decision_summary = workflow_summary.get("decision_reason_summary") or {}
    coverage = workflow_summary.get("coverage_summary") or {}
    auth = workflow_summary.get("auth_diagnostics_summary") or {}

    gate_decision = gate.get("decision") or workflow_summary.get("gate_decision") or "unknown"
    blocker_categories = _list_strings(
        decision_summary.get("blocker_categories")
        or decision_summary.get("reason_codes")
        or gate.get("reasons")
        or workflow_summary.get("gate_reasons")
    )
    next_evidence = _next_evidence_needed(coverage, auth, gate_decision)
    summary = {
        "schema_version": SUBJECT_SCHEMA_VERSION,
        "subject_id": subject_id,
        "batch_status": batch_status,
        "gate_decision": gate_decision if gate_decision in {"approve", "review", "block"} else "unknown",
        "fixture_count": int(workflow_summary.get("fixture_count") or 0),
        "redthread_replay_passed": bool(redthread.get("passed", workflow_summary.get("redthread_replay_passed", False))),
        "dryrun_executed": bool(workflow_summary.get("redthread_dryrun_executed", False)),
        "auth_surface_present": bool(auth.get("auth_surface_present", coverage.get("auth_surface_present", False))),
        "write_surface_present": bool(coverage.get("write_surface_present", coverage.get("write_coverage_present", False))),
        "boundary_evidence_present": bool(coverage.get("boundary_evidence_present", False)),
        "live_execution_performed": False,
        "confirmed_security_finding": bool(decision_summary.get("confirmed_security_finding", False)),
        "primary_blocker_categories": blocker_categories,
        "next_evidence_needed": next_evidence,
    }
    return summary


def marker_audit(text: str) -> dict[str, Any]:
    lowered = text.casefold()
    marker_hits = [marker for marker in SENSITIVE_MARKERS if marker.casefold() in lowered]
    raw_field_hits = [field for field in FORBIDDEN_RAW_FIELD_KEYS if f'"{field}"' in lowered]
    return {
        "marker_set": "configured_sensitive_marker_set_plus_har_batch_raw_field_keys",
        "marker_count": len(SENSITIVE_MARKERS),
        "marker_hit_count": len(marker_hits),
        "raw_field_key_count": len(FORBIDDEN_RAW_FIELD_KEYS),
        "raw_field_hit_count": len(raw_field_hits),
        "passed": not marker_hits and not raw_field_hits,
        "markers": sorted(set(marker_hits)),
        "raw_field_keys": sorted(set(raw_field_hits)),
    }


def _generated_subject_artifact_text(subject_dir: Path) -> str:
    chunks: list[str] = []
    for path in sorted(subject_dir.iterdir()):
        if path.name == "privacy_audit.json" or path.suffix not in {".json", ".md"}:
            continue
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _write_sanitized_subject_artifacts(work_dir: Path, subject_dir: Path, summary: dict[str, Any]) -> None:
    gate = _load_optional(work_dir / "gate_verdict.json") or {}
    sanitized_gate = {
        "decision": summary.get("gate_decision", "unknown"),
        "reason_count": len(_list_strings(gate.get("reasons"))),
        "raw_input_values_persisted": False,
    }
    workflow_summary = _load_optional(work_dir / "workflow_summary.json") or {}
    sanitized_workflow = {
        "fixture_count": summary.get("fixture_count", 0),
        "gate_decision": summary.get("gate_decision", "unknown"),
        "redthread_replay_passed": summary.get("redthread_replay_passed", False),
        "redthread_dryrun_executed": summary.get("dryrun_executed", False),
        "live_safe_replay_executed": False,
        "live_workflow_replay_executed": False,
        "live_execution_performed": False,
        "decision_reason_count": len(_list_strings((workflow_summary.get("decision_reason_summary") or {}).get("reason_codes"))),
        "raw_input_values_persisted": False,
    }
    _write_json(subject_dir / "gate_verdict.json", sanitized_gate)
    _write_json(subject_dir / "workflow_summary.json", sanitized_workflow)
    report_path = work_dir / "evidence_report.md"
    if report_path.exists():
        _write_text(subject_dir / "evidence_report.md", report_path.read_text(encoding="utf-8"))


def _discover_inputs(*, input_dir: str | Path | None, manifest: str | Path | None) -> list[Path]:
    if bool(input_dir) == bool(manifest):
        raise ValueError("supply exactly one of --input-dir or --manifest")
    if input_dir:
        root = Path(input_dir)
        return sorted(path for path in root.iterdir() if path.is_file() and path.suffix.casefold() == ".har")
    manifest_path = Path(manifest)
    payload = _load(manifest_path)
    entries = payload.get("inputs", []) if isinstance(payload, dict) else payload
    base_dir = manifest_path.resolve().parent
    paths: list[Path] = []
    for entry in entries:
        if not str(entry).casefold().endswith(".har"):
            continue
        path = Path(entry)
        paths.append(path if path.is_absolute() else base_dir / path)
    return paths


def _build_batch_artifacts(
    subjects: list[dict[str, Any]],
    *,
    total_inputs: int,
    discovered_input_count: int,
    limit: int | None,
    ingestion: str,
) -> dict[str, Any]:
    gate_counts = Counter(s.get("gate_decision", "unknown") for s in subjects if s.get("batch_status") == "processed")
    status_counts = Counter(s.get("batch_status", "unknown") for s in subjects)
    blocker_counts = Counter(item for s in subjects for item in s.get("primary_blocker_categories", []))
    next_counts = Counter(item for s in subjects for item in s.get("next_evidence_needed", []))
    batch_manifest = {
        "schema_version": BATCH_SCHEMA_VERSION,
        "batch_status": _batch_status(subjects),
        "ingestion": ingestion,
        "discovered_input_count": discovered_input_count,
        "input_count": total_inputs,
        "limit_applied": limit is not None,
        "limit": limit,
        "subject_count": len(subjects),
        "live_execution_performed": False,
        "gate_decision_counts": dict(sorted(gate_counts.items())),
        "batch_status_counts": dict(sorted(status_counts.items())),
        "raw_input_values_persisted": False,
    }
    subject_index = {
        "schema_version": BATCH_SCHEMA_VERSION,
        "subjects": subjects,
    }
    aggregate = {
        "schema_version": BATCH_SCHEMA_VERSION,
        "gate_decision_counts": dict(sorted(gate_counts.items())),
        "batch_status_counts": dict(sorted(status_counts.items())),
        "blocker_category_counts": dict(sorted(blocker_counts.items())),
        "next_evidence_counts": dict(sorted(next_counts.items())),
        "auth_surface_subject_count": sum(1 for s in subjects if s.get("auth_surface_present")),
        "write_surface_subject_count": sum(1 for s in subjects if s.get("write_surface_present")),
        "missing_boundary_evidence_subject_count": sum(1 for s in subjects if not s.get("boundary_evidence_present")),
        "confirmed_security_finding_count": sum(1 for s in subjects if s.get("confirmed_security_finding")),
        "live_execution_performed": False,
    }
    return {
        "batch_manifest.json": batch_manifest,
        "batch_manifest.md": _batch_manifest_markdown(batch_manifest),
        "subject_index.json": subject_index,
        "subject_index.md": _subject_index_markdown(subjects),
        "aggregate_blockers.json": aggregate,
        "aggregate_blockers.md": _aggregate_markdown(aggregate),
        "engine_gaps.md": _engine_gaps_markdown(aggregate),
    }


def _batch_status(subjects: list[dict[str, Any]]) -> str:
    if not subjects:
        return "no_inputs"
    if all(s.get("batch_status") == "processed" for s in subjects):
        return "complete"
    return "complete_with_non_processed_subjects"


def _privacy_blocked_subject_summary(subject_id: str, audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SUBJECT_SCHEMA_VERSION,
        "subject_id": subject_id,
        "batch_status": "privacy_blocked",
        "gate_decision": "unknown",
        "fixture_count": 0,
        "redthread_replay_passed": False,
        "dryrun_executed": False,
        "auth_surface_present": False,
        "write_surface_present": False,
        "boundary_evidence_present": False,
        "live_execution_performed": False,
        "confirmed_security_finding": False,
        "primary_blocker_categories": ["privacy_audit_failed"],
        "next_evidence_needed": ["remove_raw_values_or_sensitive_markers_from_generated_artifacts"],
        "privacy_audit": audit,
    }


def _replace_subject_with_privacy_block(subject_dir: Path, summary: dict[str, Any], audit: dict[str, Any]) -> None:
    for path in subject_dir.iterdir():
        if path.is_file() and path.suffix in {".json", ".md"}:
            path.unlink()
    _write_json(subject_dir / "privacy_audit.json", audit)
    _write_json(subject_dir / "subject_summary.json", summary)
    _write_text(subject_dir / "subject_summary.md", _subject_summary_markdown(summary))


def _failed_subject_summary(subject_id: str, exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": SUBJECT_SCHEMA_VERSION,
        "subject_id": subject_id,
        "batch_status": "failed",
        "gate_decision": "unknown",
        "fixture_count": 0,
        "redthread_replay_passed": False,
        "dryrun_executed": False,
        "auth_surface_present": False,
        "write_surface_present": False,
        "boundary_evidence_present": False,
        "live_execution_performed": False,
        "confirmed_security_finding": False,
        "primary_blocker_categories": ["subject_processing_failed"],
        "next_evidence_needed": ["rerun_subject_after_input_or_bridge_fix"],
        "failure_class": exc.__class__.__name__,
    }


def _next_evidence_needed(coverage: dict[str, Any], auth: dict[str, Any], decision: str) -> list[str]:
    needed: list[str] = []
    if auth.get("auth_surface_present") or coverage.get("auth_surface_present"):
        needed.append("approved_non_production_auth_context_if_execution_is_required")
    if coverage.get("write_surface_present") or coverage.get("write_coverage_present"):
        needed.append("approved_non_production_write_context_if_execution_is_required")
    if not coverage.get("boundary_evidence_present", False):
        needed.append("boundary_context_or_boundary_execution_evidence_if_release_requires_it")
    if decision in {"review", "block"}:
        needed.append("formal_reviewer_observation_summary")
    return sorted(set(needed))


def _subject_summary_markdown(summary: dict[str, Any]) -> str:
    return "\n".join([
        f"# HAR Batch Subject {summary['subject_id']}",
        "",
        f"- Batch status: `{summary.get('batch_status')}`",
        f"- Gate decision: `{summary.get('gate_decision')}`",
        f"- Fixture count: `{summary.get('fixture_count')}`",
        f"- RedThread replay passed: `{summary.get('redthread_replay_passed')}`",
        f"- Dry-run executed: `{summary.get('dryrun_executed')}`",
        f"- Auth surface present: `{summary.get('auth_surface_present')}`",
        f"- Write surface present: `{summary.get('write_surface_present')}`",
        f"- Boundary evidence present: `{summary.get('boundary_evidence_present')}`",
        f"- Live execution performed: `{summary.get('live_execution_performed')}`",
        f"- Confirmed security finding: `{summary.get('confirmed_security_finding')}`",
        f"- Blocker categories: `{', '.join(summary.get('primary_blocker_categories', [])) or 'none'}`",
        f"- Next evidence needed: `{', '.join(summary.get('next_evidence_needed', [])) or 'none'}`",
        "",
        "This is a sanitized offline batch summary. It is not execution proof, validation, release approval, or a confirmed finding by itself.",
        "",
    ])


def _batch_manifest_markdown(manifest: dict[str, Any]) -> str:
    return "\n".join([
        "# HAR Evidence Batch Manifest",
        "",
        f"- Batch status: `{manifest['batch_status']}`",
        f"- Discovered input count: `{manifest['discovered_input_count']}`",
        f"- Input count: `{manifest['input_count']}`",
        f"- Limit applied: `{manifest['limit_applied']}`",
        f"- Subject count: `{manifest['subject_count']}`",
        f"- Live execution performed: `{manifest['live_execution_performed']}`",
        f"- Raw input values persisted: `{manifest['raw_input_values_persisted']}`",
        f"- Gate decision counts: `{manifest['gate_decision_counts']}`",
        f"- Batch status counts: `{manifest['batch_status_counts']}`",
        "",
    ])


def _subject_index_markdown(subjects: list[dict[str, Any]]) -> str:
    lines = ["# HAR Evidence Batch Subject Index", "", "| Subject | Batch status | Gate decision | Fixtures |", "|---|---|---:|---:|"]
    for subject in subjects:
        lines.append(f"| `{subject['subject_id']}` | `{subject.get('batch_status')}` | `{subject.get('gate_decision')}` | `{subject.get('fixture_count')}` |")
    lines.append("")
    return "\n".join(lines)


def _aggregate_markdown(aggregate: dict[str, Any]) -> str:
    return "\n".join([
        "# HAR Evidence Batch Aggregate Blockers",
        "",
        f"- Gate decision counts: `{aggregate['gate_decision_counts']}`",
        f"- Batch status counts: `{aggregate['batch_status_counts']}`",
        f"- Blocker category counts: `{aggregate['blocker_category_counts']}`",
        f"- Next evidence counts: `{aggregate['next_evidence_counts']}`",
        f"- Auth surface subject count: `{aggregate['auth_surface_subject_count']}`",
        f"- Write surface subject count: `{aggregate['write_surface_subject_count']}`",
        f"- Missing boundary evidence subject count: `{aggregate['missing_boundary_evidence_subject_count']}`",
        f"- Confirmed security finding count: `{aggregate['confirmed_security_finding_count']}`",
        f"- Live execution performed: `{aggregate['live_execution_performed']}`",
        "",
        "These counts are batch observations only. They do not create findings, validation, regression proof, or release approval.",
        "",
    ])


def _engine_gaps_markdown(aggregate: dict[str, Any]) -> str:
    lines = ["# HAR Evidence Batch Engine Gaps", ""]
    if aggregate["next_evidence_counts"]:
        lines.append("## Repeated missing evidence")
        lines.append("")
        for name, count in aggregate["next_evidence_counts"].items():
            lines.append(f"- `{name}`: `{count}` subjects")
    else:
        lines.append("No repeated missing-evidence categories were observed in this batch.")
    lines.extend(["", "This file is a planning aid for engine work, not a scanner finding list.", ""])
    return "\n".join(lines)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional(path: Path) -> Any:
    if not path.exists():
        return None
    return _load(path)


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _list_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return sorted({str(item) for item in value if item})
    if isinstance(value, str) and value:
        return [value]
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an offline-only HAR evidence batch through the bridge pipeline.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-dir", help="Directory of local .har inputs")
    source.add_argument("--manifest", help="JSON list or object with inputs[] of local .har paths")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ingestion", choices=["zapi"], default="zapi")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false")
    parser.set_defaults(fail_on_marker_hit=True)
    parser.add_argument("--redthread-python", default=str(DEFAULT_REDTHREAD_PYTHON))
    parser.add_argument("--redthread-src", default=str(DEFAULT_REDTHREAD_SRC))
    args = parser.parse_args()

    manifest = run_har_evidence_batch(
        input_dir=args.input_dir,
        manifest=args.manifest,
        output_dir=args.output_dir,
        ingestion=args.ingestion,
        limit=args.limit,
        fail_fast=args.fail_fast,
        fail_on_marker_hit=args.fail_on_marker_hit,
        redthread_python=args.redthread_python,
        redthread_src=args.redthread_src,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

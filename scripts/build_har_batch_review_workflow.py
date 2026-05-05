#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_sanitized_intent_review import build_sanitized_intent_review
from scripts.run_har_evidence_batch import marker_audit

SCHEMA_VERSION = "adopt_redthread.har_batch_review_workflow.v1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _priority_subjects(subjects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        subjects,
        key=lambda s: (
            s.get("batch_status") != "processed",
            s.get("gate_decision") not in {"review", "block"},
            -int(s.get("fixture_count") or 0),
            s.get("subject_id", ""),
        ),
    )


def build_har_batch_review_workflow(batch_dir: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    batch_dir = Path(batch_dir)
    output_dir = Path(output_dir) if output_dir else batch_dir / "review_workflow"

    manifest = _read_json(batch_dir / "batch_manifest.json")
    aggregate = _read_json(batch_dir / "aggregate_blockers.json")
    subject_index = _read_json(batch_dir / "subject_index.json")
    subjects = _priority_subjects(subject_index.get("subjects", []))

    reviewer_subjects = [
        {
            "subject_id": s.get("subject_id"),
            "priority": i + 1,
            "batch_status": s.get("batch_status"),
            "gate_decision": s.get("gate_decision"),
            "fixture_count": s.get("fixture_count"),
            "next_evidence_needed": s.get("next_evidence_needed", []),
            "subject_artifact_count": s.get("subject_artifact_count"),
            "allowed_artifacts": [
                name for name in s.get("subject_artifacts", [])
                if name in {"evidence_report.md", "gate_verdict.json", "workflow_summary.json", "subject_summary.json", "subject_summary.md", "privacy_audit.json"}
            ],
        }
        for i, s in enumerate(subjects)
    ]

    phase1 = {
        "schema_version": SCHEMA_VERSION,
        "phase": "phase_1_reviewer_validation",
        "status": "ready_for_human_review_collection" if reviewer_subjects else "no_subjects",
        "source_batch_status": manifest.get("batch_status"),
        "reviewer_subjects": reviewer_subjects,
        "raw_har_review_allowed": False,
        "raw_input_paths_persisted": False,
        "required_output": "formal_reviewer_observation_summary",
    }
    phase2 = {
        "schema_version": SCHEMA_VERSION,
        "phase": "phase_2_boundary_evidence_planning",
        "status": "blocked_until_explicit_non_production_boundary_context" if aggregate.get("missing_boundary_evidence_subject_count", 0) else "not_required_by_batch",
        "missing_boundary_evidence_subject_count": aggregate.get("missing_boundary_evidence_subject_count", 0),
        "boundary_probe_executed": False,
        "live_execution_performed": False,
        "next_step": "prepare_separate_sanitized_boundary_context_request_if_release_requires_it",
    }
    phase3 = {
        "schema_version": SCHEMA_VERSION,
        "phase": "phase_3_approved_non_production_replay_proof",
        "status": "blocked_until_explicit_scoped_execution_approval",
        "approved_replay_executed": False,
        "live_execution_performed": False,
        "approval_scope_required": ["non_production_environment", "explicit_case_ids", "explicit_modes", "timeboxed_operator_approval"],
        "wildcard_scope_allowed": False,
    }
    phase4 = {
        "schema_version": SCHEMA_VERSION,
        "phase": "phase_4_batch_triage_automation",
        "status": "complete_for_current_batch",
        "recommended_batch_next_step": aggregate.get("recommended_batch_next_step"),
        "followup_subject_count": aggregate.get("followup_subject_count"),
        "evidence_review_subject_count": aggregate.get("evidence_review_subject_count"),
        "remediation_subject_count": aggregate.get("remediation_subject_count"),
        "priority_subject_ids": [s["subject_id"] for s in reviewer_subjects],
    }
    release_ready = (
        manifest.get("batch_status") == "complete"
        and not aggregate.get("followup_required", True)
        and aggregate.get("subject_privacy_failed_count") == 0
        and aggregate.get("confirmed_security_finding_count") == 0
    )
    phase5 = {
        "schema_version": SCHEMA_VERSION,
        "phase": "phase_5_release_readiness_gate",
        "release_readiness": "ready" if release_ready else "not_ready",
        "blocking_requirements": [] if release_ready else [
            "formal_reviewer_observation_summary",
            "boundary_context_or_boundary_execution_evidence_if_release_requires_it",
        ],
        "gate_decision_counts": manifest.get("gate_decision_counts", {}),
        "privacy_audit_passed": aggregate.get("subject_privacy_failed_count") == 0,
        "live_execution_performed": False,
    }
    intent_review_result = build_sanitized_intent_review(batch_dir, batch_dir / "intent_review", fail_on_marker_hit=True)
    phase6 = {
        "schema_version": SCHEMA_VERSION,
        "phase": "phase_6_sanitized_intent_review",
        "status": "complete_for_current_batch",
        "intent_review_output_dir": "intent_review",
        "intent_review_artifacts": [
            "intent_review_context.json",
            "intent_review.json",
            "intent_review.md",
            "redthread_evidence_export.json",
            "advancement_summary.json",
            "advancement_summary.md",
            "business_validation_plan.json",
            "schema_validation.json",
            "redthread_evidence_contract_preview.json",
            "privacy_audit.json",
        ],
        "subject_count": intent_review_result.get("subject_count"),
        "agent_mode": intent_review_result.get("agent_mode"),
        "live_execution_performed": False,
        "redthread_evaluation_required": True,
        "confirmed_security_finding_claimed": False,
    }

    artifacts = {
        "phase_1_reviewer_packet.json": phase1,
        "phase_1_reviewer_packet.md": _phase1_md(phase1),
        "phase_2_boundary_plan.json": phase2,
        "phase_2_boundary_plan.md": _kv_md("Phase 2 Boundary Evidence Plan", phase2),
        "phase_3_approved_replay_plan.json": phase3,
        "phase_3_approved_replay_plan.md": _kv_md("Phase 3 Approved Replay Plan", phase3),
        "phase_4_batch_triage_automation.json": phase4,
        "phase_4_batch_triage_automation.md": _kv_md("Phase 4 Batch Triage Automation", phase4),
        "phase_5_readiness_gate.json": phase5,
        "phase_5_readiness_gate.md": _kv_md("Phase 5 Readiness Gate", phase5),
        "phase_6_sanitized_intent_review.json": phase6,
        "phase_6_sanitized_intent_review.md": _kv_md("Phase 6 Sanitized Intent Review", phase6),
    }

    audit_text = "\n".join(json.dumps(v, sort_keys=True) if isinstance(v, dict) else v for v in artifacts.values())
    audit = marker_audit(audit_text)
    artifacts["privacy_audit.json"] = audit
    if not audit["passed"]:
        _write_json(output_dir / "privacy_audit.json", audit)
        raise RuntimeError("HAR batch review workflow privacy audit failed")

    for filename, payload in artifacts.items():
        if filename.endswith(".json"):
            _write_json(output_dir / filename, payload)  # type: ignore[arg-type]
        else:
            _write_text(output_dir / filename, str(payload))
    return {"schema_version": SCHEMA_VERSION, "output_dir": str(output_dir), "artifact_count": len(artifacts), "privacy_audit": audit}


def _phase1_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase 1 Reviewer Packet",
        "",
        "Sanitized batch evidence only. Do not review raw HARs or raw input paths.",
        "",
        f"- Status: `{payload['status']}`",
        f"- Required output: `{payload['required_output']}`",
        "",
        "| Priority | Subject | Status | Gate | Fixtures | Artifacts |",
        "|---:|---|---|---|---:|---:|",
    ]
    for s in payload["reviewer_subjects"]:
        lines.append(f"| {s['priority']} | `{s['subject_id']}` | `{s['batch_status']}` | `{s['gate_decision']}` | {s['fixture_count']} | {s['subject_artifact_count']} |")
    lines.extend(["", "Reviewer must provide written observations before any release/readiness promotion.", ""])
    return "\n".join(lines)


def _kv_md(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", ""]
    for key, value in payload.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build sanitized HAR batch phase 1-5 review workflow artifacts.")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    result = build_har_batch_review_workflow(args.batch_dir, args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

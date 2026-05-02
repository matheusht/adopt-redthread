from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_evidence_readiness import build_evidence_readiness


PASS_AUDIT = {
    "marker_hit_count": 0,
    "passed": True,
    "hit_files": [],
}


class EvidenceReadinessTests(unittest.TestCase):
    def test_waits_for_external_validation_without_changing_verdict_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_readiness_inputs(Path(tmp), readout_status="waiting_for_filled_external_observations")

            payload = build_evidence_readiness(
                **paths,
                output_dir=Path(tmp) / "out",
                regenerate_freshness=False,
                fail_on_marker_hit=True,
            )

            self.assertEqual(payload["schema_version"], "adopt_redthread.evidence_readiness.v1")
            self.assertEqual(payload["readiness_status"], "waiting_for_external_validation")
            blocker_codes = {blocker["code"] for blocker in payload["blockers"]}
            self.assertIn("external_validation_not_ready", blocker_codes)
            self.assertIn("boundary_context_not_ready", blocker_codes)
            self.assertIn("boundary_probe_not_executed", blocker_codes)
            self.assertEqual(payload["components"]["boundary_probe_context"]["context_status"], "blocked_missing_context")
            self.assertIn("does not change local bridge approve/review/block verdict semantics", " ".join(payload["non_claims"]))

    def test_boundary_context_ready_does_not_clear_probe_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_readiness_inputs(
                Path(tmp),
                readout_status="ready_for_external_validation_readout",
                boundary_context_status="ready_for_boundary_probe",
                boundary_context_valid=True,
            )

            payload = build_evidence_readiness(
                **paths,
                output_dir=Path(tmp) / "out",
                regenerate_freshness=False,
                fail_on_marker_hit=True,
            )

            self.assertEqual(payload["readiness_status"], "boundary_context_pending")
            blocker_codes = {blocker["code"] for blocker in payload["blockers"]}
            self.assertNotIn("boundary_context_not_ready", blocker_codes)
            self.assertIn("boundary_probe_not_executed", blocker_codes)
            self.assertTrue(payload["components"]["boundary_probe_context"]["boundary_probe_execution_authorized"])
            self.assertIn("ready context as execution proof", " ".join(payload["recommended_next_actions"]))

    def test_missing_boundary_context_is_required_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_readiness_inputs(Path(tmp), readout_status="ready_for_external_validation_readout")
            paths["boundary_context"] = Path(tmp) / "missing_boundary_context.json"

            payload = build_evidence_readiness(
                **paths,
                output_dir=Path(tmp) / "out",
                regenerate_freshness=False,
                fail_on_marker_hit=True,
            )

            self.assertEqual(payload["readiness_status"], "missing_required_evidence")
            self.assertIn(
                {"code": "missing_required_evidence", "component": "boundary_probe_context", "detail": "artifact is missing"},
                payload["blockers"],
            )

    def test_privacy_blocked_when_marker_audit_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_readiness_inputs(Path(tmp), readout_status="ready_for_external_validation_readout", marker_hit=True)

            payload = build_evidence_readiness(
                **paths,
                output_dir=Path(tmp) / "out",
                regenerate_freshness=False,
                fail_on_marker_hit=False,
            )

            self.assertEqual(payload["readiness_status"], "privacy_blocked")
            blocker_codes = {blocker["code"] for blocker in payload["blockers"]}
            self.assertIn("privacy_marker_audit_failed", blocker_codes)

    def test_boundary_context_failed_audit_fails_closed_without_literal_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_readiness_inputs(Path(tmp), readout_status="ready_for_external_validation_readout")
            context_payload = json.loads(paths["boundary_context"].read_text(encoding="utf-8"))
            context_payload["output_marker_audit"] = {
                "marker_hit_count": 0,
                "raw_field_hit_count": 1,
                "passed": False,
                "hit_files": [],
            }
            paths["boundary_context"].write_text(json.dumps(context_payload), encoding="utf-8")

            payload = build_evidence_readiness(
                **paths,
                output_dir=Path(tmp) / "out",
                regenerate_freshness=False,
                fail_on_marker_hit=False,
            )
            self.assertEqual(payload["readiness_status"], "privacy_blocked")
            with self.assertRaises(RuntimeError):
                build_evidence_readiness(
                    **paths,
                    output_dir=Path(tmp) / "out2",
                    regenerate_freshness=False,
                    fail_on_marker_hit=True,
                )


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _write_readiness_inputs(
    root: Path,
    *,
    readout_status: str,
    marker_hit: bool = False,
    boundary_context_status: str = "blocked_missing_context",
    boundary_context_valid: bool = False,
) -> dict[str, Path]:
    matrix = _write_json(root / "evidence_matrix.json", {
        "schema_version": "adopt_redthread.evidence_matrix.v1",
        "rows": [
            {"gate_decision": "approve"},
            {"gate_decision": "review"},
            {"gate_decision": "block"},
        ],
    })
    packet = _write_json(root / "reviewer_packet.json", {
        "schema_version": "adopt_redthread.reviewer_packet.v1",
        "sanitized_marker_audit": PASS_AUDIT,
        "handoff_completeness_audit": {"passed": True, "missing_marker_count": 0},
    })
    handoff = _write_json(root / "external_review_handoff_manifest.json", {
        "schema_version": "adopt_redthread.external_review_handoff.v1",
        "handoff_status": "ready_for_external_cold_review",
        "validation_status": "not_validation_until_filled_observations_are_summarized",
        "target_review_count": 3,
        "protocol": {"allowed_artifacts": ["evidence_report.md"]},
        "input_marker_audit": PASS_AUDIT,
        "output_marker_audit": PASS_AUDIT,
    })
    batch = _write_json(root / "external_review_session_batch.json", {
        "schema_version": "adopt_redthread.external_review_session_batch.v1",
        "session_status": "ready_for_external_reviewer_distribution",
        "validation_status": "not_validation_until_filled_observations_are_summarized",
        "target_review_count": 3,
        "sessions": [{"session_id": "review_1"}, {"session_id": "review_2"}, {"session_id": "review_3"}],
        "input_marker_audit": PASS_AUDIT,
        "output_marker_audit": PASS_AUDIT,
    })
    audit = {"marker_hit_count": 1, "passed": False, "hit_files": ["example"]} if marker_hit else PASS_AUDIT
    readout = _write_json(root / "external_validation_readout.json", {
        "schema_version": "adopt_redthread.external_validation_readout.v1",
        "readout_status": readout_status,
        "validation_claim": "not_external_validation_until_required_complete_sanitized_observation_summaries_exist",
        "target_review_count": 3,
        "rollup_summary": {
            "complete_summary_count": 0 if readout_status != "ready_for_external_validation_readout" else 3,
            "missing_or_invalid_file_count": 3 if readout_status != "ready_for_external_validation_readout" else 0,
        },
        "sanitized_marker_audit": audit,
    })
    boundary_context = _write_json(root / "tenant_user_boundary_probe_context.template.json", {
        "schema_version": "adopt_redthread.boundary_probe_context.v1",
        "context_status": boundary_context_status,
        "boundary_probe_execution_authorized": boundary_context_status == "ready_for_boundary_probe",
        "boundary_probe_executed": False,
        "gate_decision": "review",
        "confirmed_security_finding": False,
        "verdict_semantics_changed": False,
        "validation": {
            "valid": boundary_context_valid,
            "blocker_count": 0 if boundary_context_valid else 1,
            "blockers": [] if boundary_context_valid else [{"code": "missing_context", "detail": "No sanitized boundary probe context was supplied."}],
        },
        "input_marker_audit": PASS_AUDIT,
        "output_marker_audit": PASS_AUDIT,
    })
    boundary = _write_json(root / "tenant_user_boundary_probe_result.json", {
        "schema_version": "adopt_redthread.boundary_probe_result.v1",
        "result_status": "blocked_missing_context",
        "boundary_probe_executed": False,
        "gate_decision": "review",
        "confirmed_security_finding": False,
        "verdict_semantics_changed": False,
        "configured_sensitive_marker_check": PASS_AUDIT,
    })
    freshness = _write_json(root / "evidence_freshness_manifest.json", {
        "schema_version": "adopt_redthread.evidence_freshness_manifest.v1",
        "freshness_status": "fresh",
        "summary": {"copy_check_count": 4, "problem_count": 0},
        "sanitized_marker_audit": PASS_AUDIT,
    })
    return {
        "evidence_matrix": matrix,
        "reviewer_packet": packet,
        "handoff_manifest": handoff,
        "session_batch": batch,
        "validation_readout": readout,
        "boundary_context": boundary_context,
        "boundary_result": boundary,
        "freshness_manifest": freshness,
    }


if __name__ == "__main__":
    unittest.main()

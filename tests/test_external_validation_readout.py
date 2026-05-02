from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_external_validation_readout import build_external_validation_readout


class ExternalValidationReadoutTests(unittest.TestCase):
    def test_waits_for_missing_external_observations_without_claiming_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "external_review_session_batch.json"
            _write_batch(batch, [root / "review_1" / "reviewer_observation_summary.json"])

            readout = build_external_validation_readout(batch_manifest=batch, output_dir=root / "readout")
            readout_md = (root / "readout" / "external_validation_readout.md").read_text(encoding="utf-8")

        self.assertEqual(readout["schema_version"], "adopt_redthread.external_validation_readout.v1")
        self.assertEqual(readout["readout_status"], "waiting_for_filled_external_observations")
        self.assertEqual(readout["validation_claim"], "not_external_validation_until_required_complete_sanitized_observation_summaries_exist")
        self.assertIn("does not prove buyer demand", readout_md)

    def test_ready_when_three_complete_sanitized_summaries_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_paths = []
            for index in range(3):
                path = root / f"review_{index + 1}" / "reviewer_observation_summary.json"
                path.parent.mkdir(parents=True)
                _write_summary(path, decision="review")
                summary_paths.append(path)
            batch = root / "external_review_session_batch.json"
            _write_batch(batch, summary_paths, include_boundary_context_request=True)

            readout = build_external_validation_readout(batch_manifest=batch, output_dir=root / "readout")
            readout_json = (root / "readout" / "external_validation_readout.json").read_text(encoding="utf-8")
            readout_md = (root / "readout" / "external_validation_readout.md").read_text(encoding="utf-8")

        self.assertEqual(readout["readout_status"], "ready_for_external_validation_readout")
        self.assertEqual(readout["validation_claim"], "external_human_validation_readout_ready_but_not_buyer_demand_or_production_readiness_proof")
        self.assertEqual(readout["rollup_summary"]["complete_summary_count"], 3)
        self.assertEqual(readout["rollup_summary"]["decision_counts"]["review"], 3)
        self.assertEqual(readout["review_input_coverage"]["boundary_context_request_delivery_status"], "delivered_to_all_sessions")
        self.assertFalse(readout["review_input_coverage"]["boundary_context_request_is_execution_proof"])
        self.assertIn("Boundary context request is execution proof: `False`", readout_md)
        self.assertNotIn("authorization:", readout_json)

    def test_marker_hit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "review_1" / "reviewer_observation_summary.json"
            summary.parent.mkdir(parents=True)
            _write_summary(summary, decision="review", unclear="authorization: leaked")
            batch = root / "external_review_session_batch.json"
            _write_batch(batch, [summary])

            with self.assertRaises(RuntimeError):
                build_external_validation_readout(batch_manifest=batch, output_dir=root / "readout")


def _write_batch(path: Path, summary_paths: list[Path], *, include_boundary_context_request: bool = False) -> None:
    sessions = []
    for index, summary_path in enumerate(summary_paths):
        session = {
            "session_id": f"review_{index + 1}",
            "expected_summary_path": str(summary_path),
        }
        if include_boundary_context_request:
            session["allowed_artifacts"] = {
                "tenant_user_boundary_probe_context_request.md": {
                    "path": str(summary_path.parent / "artifacts" / "tenant_user_boundary_probe_context_request.md"),
                    "sha256": "test-sha",
                    "byte_count": 10,
                    "line_count": 1,
                }
            }
        sessions.append(session)
    payload = {
        "schema_version": "adopt_redthread.external_review_session_batch.v1",
        "target_review_count": 3,
        "sessions": sessions,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_summary(path: Path, *, decision: str, unclear: str = "none recorded") -> None:
    payload = {
        "schema_version": "adopt_redthread.reviewer_observation_summary.v1",
        "completion_summary": {
            "complete": True,
            "observation_status": "ready_for_review_signal",
        },
        "validation_signals": {
            "release_decision": decision,
            "decision_consistency": "consistent",
            "behavior_change_recorded": True,
            "next_probe_requested": False,
            "wants_repeat_review": True,
        },
        "confusion_summary": {
            "has_confusion_or_weakness": unclear != "none recorded",
            "unclear_or_weak_evidence": unclear,
            "next_probe_requested": "none recorded",
        },
        "sanitized_marker_audit": {
            "passed": "authorization:" not in unclear,
            "marker_hit_count": 1 if "authorization:" in unclear else 0,
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_har_evidence_batch import build_subject_summary, marker_audit, run_har_evidence_batch


class HarEvidenceBatchTests(unittest.TestCase):
    def test_multiple_inputs_generate_subject_dirs_and_preserve_gate_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "captures"
            input_dir.mkdir()
            (input_dir / "one.har").write_text("{}", encoding="utf-8")
            (input_dir / "two.har").write_text("{}", encoding="utf-8")
            (input_dir / "ignore.txt").write_text("ignored", encoding="utf-8")
            output_dir = root / "batch"

            def fake_workflow(input_path, *, output_dir, **kwargs):
                self.assertFalse(kwargs["run_live_safe_replay"])
                self.assertFalse(kwargs["run_live_workflow_replay"])
                self.assertIsNone(kwargs["auth_context"])
                self.assertFalse(kwargs["allow_reviewed_auth"])
                self.assertIsNone(kwargs["write_context"])
                self.assertFalse(kwargs["allow_reviewed_writes"])
                decision = "approve" if str(input_path).endswith("one.har") else "block"
                Path(output_dir, "workflow_summary.json").write_text(json.dumps({
                    "fixture_count": 2,
                    "gate_decision": decision,
                    "redthread_replay_passed": decision == "approve",
                    "redthread_dryrun_executed": True,
                    "coverage_summary": {"write_surface_present": decision == "block", "boundary_evidence_present": False},
                    "auth_diagnostics_summary": {"auth_surface_present": False},
                    "decision_reason_summary": {"reason_codes": ["missing_boundary_evidence"] if decision == "block" else []},
                }), encoding="utf-8")
                Path(output_dir, "gate_verdict.json").write_text(json.dumps({"decision": decision}), encoding="utf-8")
                return {"gate_decision": decision}

            with patch("scripts.run_har_evidence_batch.run_bridge_workflow", side_effect=fake_workflow), patch("scripts.run_har_evidence_batch.build_evidence_report"):
                manifest = run_har_evidence_batch(input_dir=input_dir, output_dir=output_dir, redthread_python="python", redthread_src="src")

            self.assertEqual(manifest["subject_count"], 2)
            self.assertEqual(manifest["gate_decision_counts"], {"approve": 1, "block": 1})
            self.assertTrue((output_dir / "subjects" / "subject_001" / "subject_summary.json").exists())
            self.assertTrue((output_dir / "subjects" / "subject_002" / "subject_summary.md").exists())
            subject_two = json.loads((output_dir / "subjects" / "subject_002" / "subject_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(subject_two["gate_decision"], "block")
            self.assertEqual(subject_two["batch_status"], "processed")
            self.assertFalse(subject_two["live_execution_performed"])

    def test_failed_input_becomes_failed_batch_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "captures"
            input_dir.mkdir()
            (input_dir / "bad.har").write_text("{}", encoding="utf-8")
            output_dir = root / "batch"

            with patch("scripts.run_har_evidence_batch.run_bridge_workflow", side_effect=ValueError("bad raw input")):
                manifest = run_har_evidence_batch(input_dir=input_dir, output_dir=output_dir, redthread_python="python", redthread_src="src")

            self.assertEqual(manifest["batch_status_counts"], {"failed": 1})
            subject = json.loads((output_dir / "subjects" / "subject_001" / "subject_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(subject["batch_status"], "failed")
            self.assertEqual(subject["gate_decision"], "unknown")
            self.assertIn("subject_processing_failed", subject["primary_blocker_categories"])

    def test_subject_summary_has_no_new_gate_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subject_dir = Path(tmp)
            (subject_dir / "workflow_summary.json").write_text(json.dumps({"gate_decision": "review-needed"}), encoding="utf-8")
            summary = build_subject_summary("subject_001", subject_dir, batch_status="skipped")
            self.assertEqual(summary["batch_status"], "skipped")
            self.assertEqual(summary["gate_decision"], "unknown")

    def test_marker_audit_rejects_sensitive_markers_and_raw_keys(self) -> None:
        audit = marker_audit('{"headers": "redacted", "note": "authorization: value"}')
        self.assertFalse(audit["passed"])
        self.assertGreaterEqual(audit["marker_hit_count"], 1)
        self.assertIn("headers", audit["raw_field_keys"])

    def test_privacy_blocked_subject_causes_failure_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "captures"
            input_dir.mkdir()
            (input_dir / "one.har").write_text("{}", encoding="utf-8")
            output_dir = root / "batch"

            def fake_workflow(_input_path, *, output_dir, **_kwargs):
                Path(output_dir, "workflow_summary.json").write_text(json.dumps({
                    "fixture_count": 1,
                    "gate_decision": "block",
                    "decision_reason_summary": {"reason_codes": ["authorization:"]},
                }), encoding="utf-8")
                Path(output_dir, "gate_verdict.json").write_text(json.dumps({"decision": "block"}), encoding="utf-8")
                return {}

            with patch("scripts.run_har_evidence_batch.run_bridge_workflow", side_effect=fake_workflow), patch("scripts.run_har_evidence_batch.build_evidence_report"):
                with self.assertRaises(RuntimeError):
                    run_har_evidence_batch(input_dir=input_dir, output_dir=output_dir, redthread_python="python", redthread_src="src")

            subject = json.loads((output_dir / "subjects" / "subject_001" / "subject_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(subject["batch_status"], "privacy_blocked")


if __name__ == "__main__":
    unittest.main()

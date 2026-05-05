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
                    "request_blueprint": {"url": "https://example.invalid/raw", "headers": ["cookie"]},
                }), encoding="utf-8")
                Path(output_dir, "gate_verdict.json").write_text(json.dumps({"decision": decision}), encoding="utf-8")
                Path(output_dir, "fixture_bundle.json").write_text(json.dumps({"url": "https://example.invalid/raw"}), encoding="utf-8")
                return {"gate_decision": decision}

            with patch("scripts.run_har_evidence_batch.run_bridge_workflow", side_effect=fake_workflow), patch("scripts.run_har_evidence_batch.build_evidence_report"):
                manifest = run_har_evidence_batch(input_dir=input_dir, output_dir=output_dir, redthread_python="python", redthread_src="src")

            self.assertEqual(manifest["subject_count"], 2)
            self.assertEqual(manifest["input_source_type"], "input_dir")
            self.assertFalse(manifest["raw_input_paths_persisted"])
            self.assertEqual(manifest["gate_decision_counts"], {"approve": 1, "block": 1})
            self.assertEqual(manifest["execution_controls"], {
                "live_safe_replay": False,
                "live_workflow_replay": False,
                "reviewed_auth": False,
                "reviewed_writes": False,
                "boundary_probe": False,
            })
            self.assertTrue((output_dir / "subjects" / "subject_001" / "subject_summary.json").exists())
            self.assertTrue((output_dir / "subjects" / "subject_002" / "subject_summary.md").exists())
            subject_two = json.loads((output_dir / "subjects" / "subject_002" / "subject_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(subject_two["gate_decision"], "block")
            self.assertEqual(subject_two["batch_status"], "processed")
            self.assertFalse(subject_two["live_execution_performed"])
            subject_files = {path.name for path in (output_dir / "subjects" / "subject_001").iterdir()}
            self.assertNotIn("fixture_bundle.json", subject_files)
            workflow = json.loads((output_dir / "subjects" / "subject_001" / "workflow_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(workflow["raw_input_values_persisted"], False)
            self.assertNotIn("request_blueprint", workflow)
            aggregate = json.loads((output_dir / "aggregate_blockers.json").read_text(encoding="utf-8"))
            self.assertTrue(aggregate["followup_required"])
            self.assertEqual(aggregate["followup_subject_count"], 1)
            self.assertEqual(aggregate["evidence_review_subject_count"], 1)
            self.assertEqual(aggregate["remediation_subject_count"], 0)
            self.assertEqual(aggregate["recommended_batch_next_step"], "review_repeated_missing_evidence_counts")
            self.assertEqual(aggregate["processed_subject_count"], 2)
            self.assertEqual(aggregate["non_processed_subject_count"], 0)
            self.assertEqual(aggregate["subject_privacy_passed_count"], 2)
            self.assertEqual(aggregate["subject_privacy_failed_count"], 0)

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
            aggregate = json.loads((output_dir / "aggregate_blockers.json").read_text(encoding="utf-8"))
            self.assertTrue(aggregate["followup_required"])
            self.assertEqual(aggregate["followup_subject_count"], 1)
            self.assertEqual(aggregate["evidence_review_subject_count"], 0)
            self.assertEqual(aggregate["remediation_subject_count"], 1)
            self.assertEqual(aggregate["recommended_batch_next_step"], "rerun_failed_subjects_after_input_or_bridge_fix")
            self.assertEqual(aggregate["processed_subject_count"], 0)
            self.assertEqual(aggregate["non_processed_subject_count"], 1)
            self.assertEqual(aggregate["subject_privacy_passed_count"], 1)
            self.assertEqual(aggregate["subject_privacy_failed_count"], 0)

    def test_empty_input_dir_writes_no_inputs_batch_without_running_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "captures"
            input_dir.mkdir()
            output_dir = root / "batch"

            with patch("scripts.run_har_evidence_batch.run_bridge_workflow") as workflow:
                manifest = run_har_evidence_batch(input_dir=input_dir, output_dir=output_dir, redthread_python="python", redthread_src="src")

            workflow.assert_not_called()
            self.assertEqual(manifest["batch_status"], "no_inputs")
            self.assertEqual(manifest["discovered_input_count"], 0)
            self.assertEqual(manifest["input_count"], 0)
            self.assertEqual(manifest["subject_count"], 0)
            self.assertEqual(manifest["batch_status_counts"], {})
            self.assertFalse(any(manifest["execution_controls"].values()))
            aggregate = json.loads((output_dir / "aggregate_blockers.json").read_text(encoding="utf-8"))
            self.assertFalse(aggregate["followup_required"])
            self.assertEqual(aggregate["followup_subject_count"], 0)
            self.assertEqual(aggregate["evidence_review_subject_count"], 0)
            self.assertEqual(aggregate["remediation_subject_count"], 0)
            self.assertEqual(aggregate["recommended_batch_next_step"], "no_followup_required")

    def test_limit_zero_is_explicit_no_inputs_batch_with_discovered_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "captures"
            input_dir.mkdir()
            (input_dir / "one.har").write_text("{}", encoding="utf-8")
            output_dir = root / "batch"

            with patch("scripts.run_har_evidence_batch.run_bridge_workflow") as workflow:
                manifest = run_har_evidence_batch(input_dir=input_dir, output_dir=output_dir, limit=0, redthread_python="python", redthread_src="src")

            workflow.assert_not_called()
            self.assertEqual(manifest["batch_status"], "no_inputs")
            self.assertEqual(manifest["discovered_input_count"], 1)
            self.assertEqual(manifest["input_count"], 0)
            self.assertTrue(manifest["limit_applied"])
            self.assertEqual(manifest["limit"], 0)

    def test_negative_limit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "captures"
            input_dir.mkdir()
            with self.assertRaises(ValueError):
                run_har_evidence_batch(input_dir=input_dir, output_dir=root / "batch", limit=-1, redthread_python="python", redthread_src="src")

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

    def test_manifest_resolves_relative_paths_from_manifest_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_dir = root / "manifests"
            manifest_dir.mkdir()
            captures = manifest_dir / "captures"
            captures.mkdir()
            (captures / "one.har").write_text("{}", encoding="utf-8")
            (manifest_dir / "batch.json").write_text(json.dumps({"inputs": ["captures/one.har", "ignore.txt"]}), encoding="utf-8")
            output_dir = root / "batch"
            seen: list[Path] = []

            def fake_workflow(input_path, *, output_dir, **_kwargs):
                seen.append(Path(input_path))
                Path(output_dir, "workflow_summary.json").write_text(json.dumps({"fixture_count": 1, "gate_decision": "review"}), encoding="utf-8")
                Path(output_dir, "gate_verdict.json").write_text(json.dumps({"decision": "review"}), encoding="utf-8")
                return {}

            with patch("scripts.run_har_evidence_batch.run_bridge_workflow", side_effect=fake_workflow), patch("scripts.run_har_evidence_batch.build_evidence_report"):
                manifest = run_har_evidence_batch(manifest=manifest_dir / "batch.json", output_dir=output_dir, redthread_python="python", redthread_src="src")

            self.assertEqual(manifest["subject_count"], 1)
            self.assertEqual(manifest["input_source_type"], "manifest")
            self.assertFalse(manifest["raw_input_paths_persisted"])
            self.assertEqual([path.resolve() for path in seen], [(captures / "one.har").resolve()])

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

            subject_dir = output_dir / "subjects" / "subject_001"
            subject = json.loads((subject_dir / "subject_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(subject["batch_status"], "privacy_blocked")
            self.assertEqual(subject["primary_blocker_categories"], ["privacy_audit_failed"])
            self.assertFalse((subject_dir / "workflow_summary.json").exists())
            self.assertFalse((subject_dir / "gate_verdict.json").exists())
            self.assertNotIn("authorization:", (subject_dir / "subject_summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

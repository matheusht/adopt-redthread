from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_reviewed_write_reference import run_reviewed_write_reference


class ReviewedWriteReferenceTests(unittest.TestCase):
    def test_reviewed_write_reference_generates_review_evidence_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "reviewed_write_reference"
            summary = run_reviewed_write_reference(output_dir, run_dryrun=False)
            report = (output_dir / "evidence_report.md").read_text()
            gate = json.loads((output_dir / "gate_verdict.json").read_text())

        binding_summary = summary["live_workflow_binding_application_summary"]
        requirement_summary = summary["live_workflow_requirement_summary"]

        self.assertEqual(summary["fixture_count"], 5)
        self.assertEqual(summary["live_workflow_count"], 1)
        self.assertEqual(summary["live_workflow_replay_count"], 1)
        self.assertEqual(summary["live_workflow_blocked_count"], 0)
        self.assertEqual(summary["live_workflow_aborted_count"], 0)
        self.assertEqual(requirement_summary["workflow_class_counts"], {"reviewed_write_workflow": 1})
        self.assertEqual(requirement_summary["declared_response_binding_count"], 3)
        self.assertEqual(requirement_summary["applied_response_binding_count"], 3)
        self.assertEqual(binding_summary["planned_response_binding_count"], 3)
        self.assertEqual(binding_summary["applied_response_binding_count"], 3)
        self.assertEqual(binding_summary["unapplied_response_binding_count"], 0)
        self.assertTrue(summary["redthread_replay_passed"])
        self.assertFalse(summary["redthread_dryrun_executed"])
        self.assertEqual(summary["gate_decision"], "review")
        self.assertEqual(gate["warnings"], ["manual_review_required_for_write_paths"])
        self.assertIn("Local bridge gate decision: `review`", report)
        self.assertIn("RedThread replay/dry-run is evidence", report)
        self.assertIn("Approved write context required: `True`", report)
        self.assertIn("write paths are present", report)


if __name__ == "__main__":
    unittest.main()

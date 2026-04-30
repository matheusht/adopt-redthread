from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.generate_hero_binding_truth import build_hero_artifacts


class GoldenDemoTruthTests(unittest.TestCase):
    def test_hero_binding_truth_matches_documented_golden_result(self) -> None:
        generated_summary = build_hero_artifacts("runs/test_hero_binding_truth")
        binding_summary = generated_summary["live_workflow_binding_application_summary"]

        self.assertEqual(generated_summary["live_workflow_replay_count"], 1)
        self.assertEqual(binding_summary["planned_response_binding_count"], 2)
        self.assertEqual(binding_summary["applied_response_binding_count"], 2)
        self.assertEqual(binding_summary["unapplied_response_binding_count"], 0)
        self.assertEqual(binding_summary["binding_application_failure_counts"], {})
        self.assertEqual(binding_summary["failed_binding_ids"], [])
        self.assertEqual(generated_summary["gate_decision"], "approve")

        doc = Path("docs/hero-flow-binding-truth.md").read_text()
        self.assertIn('"applied_response_binding_count": 2', doc)
        self.assertIn('"unapplied_response_binding_count": 0', doc)
        self.assertIn('"binding_application_failure_counts": {}', doc)
        self.assertIn('"gate_decision": "approve"', doc)

        checked_demo_summary = Path("runs/hero_binding_truth/workflow_summary.json")
        if checked_demo_summary.exists():
            artifact_summary = json.loads(checked_demo_summary.read_text())
            self.assertEqual(artifact_summary["gate_decision"], "approve")
            self.assertEqual(artifact_summary["live_workflow_binding_application_summary"], binding_summary)


if __name__ == "__main__":
    unittest.main()

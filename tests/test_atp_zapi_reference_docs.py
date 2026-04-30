from __future__ import annotations

import json
import unittest
from pathlib import Path


class AtpZapiReferenceDocsTests(unittest.TestCase):
    def test_reference_expected_summary_preserves_review_semantics(self) -> None:
        expected_doc = json.loads(Path("fixtures/reference_demos/atp_tennis_zapi_reference_expected.json").read_text())
        expected = expected_doc["expected"]

        self.assertEqual(expected_doc["input_file_basename"], "demo_session_filtered.har")
        self.assertEqual(expected["ingestion"], "zapi")
        self.assertEqual(expected["fixture_count"], 5)
        self.assertEqual(expected["declared_response_binding_count"], 3)
        self.assertEqual(expected["applied_response_binding_count"], 3)
        self.assertTrue(expected["redthread_replay_passed"])
        self.assertEqual(expected["gate_decision"], "review")
        self.assertEqual(expected["gate_warning"], "manual_review_required_for_write_paths")

    def test_reference_docs_do_not_claim_atp_approve(self) -> None:
        doc = Path("docs/zapi-reference-demo.md").read_text()

        self.assertIn("runs/atp_tennis_01_live_bound/", doc)
        self.assertIn("make check-zapi-reference", doc)
        self.assertIn("The correct result is **review**, not approve.", doc)
        self.assertIn("manual_review_required_for_write_paths", doc)

    def test_victoria_expected_block_summary_is_sanitized(self) -> None:
        expected_doc = json.loads(Path("fixtures/reference_demos/victoria_expected_block.json").read_text())
        expected = expected_doc["expected"]

        self.assertEqual(expected_doc["input_file_basename"], "victoria_filtered.har")
        self.assertIn("no_raw_har", expected_doc["artifact_policy"])
        self.assertEqual(expected["fixture_count"], 3)
        self.assertEqual(expected["workflow_count"], 1)
        self.assertEqual(expected["gate_decision"], "block")
        self.assertEqual(expected["gate_blocker"], "live_workflow_blocked_steps_present")
        self.assertEqual(expected["workflow_reason"], "missing_write_context")
        self.assertTrue(expected["redthread_replay_passed"])


if __name__ == "__main__":
    unittest.main()

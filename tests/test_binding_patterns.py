from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.live_replay.binding_patterns import build_binding_pattern_candidates


class BindingPatternTests(unittest.TestCase):
    def test_groups_history_rows_into_review_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "binding_history.jsonl"
            output_path = Path(tmp) / "binding_pattern_candidates.json"
            rows = [
                {
                    "workflow_id": "wf-1",
                    "source_case_id": "a",
                    "source_type": "response_json",
                    "source_key": "account.id",
                    "target_field": "request_body_json",
                    "target_path": "account_id",
                    "outcome": "success",
                    "app_host": "one.example",
                },
                {
                    "workflow_id": "wf-2",
                    "source_case_id": "a",
                    "source_type": "response_json",
                    "source_key": "account.id",
                    "target_field": "request_body_json",
                    "target_path": "account_id",
                    "outcome": "success",
                    "app_host": "two.example",
                },
                {
                    "workflow_id": "wf-3",
                    "source_case_id": "a",
                    "source_type": "response_json",
                    "source_key": "account.id",
                    "target_field": "request_body_json",
                    "target_path": "account_id",
                    "outcome": "success",
                    "app_host": "three.example",
                },
            ]
            history_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            payload = build_binding_pattern_candidates(history_path, output_path=output_path)

            self.assertEqual(payload["history_row_count"], 3)
            self.assertEqual(payload["candidate_count"], 1)
            self.assertEqual(payload["promotion_ready_count"], 1)
            candidate = payload["candidates"][0]
            self.assertEqual(candidate["source_key"], "account.id")
            self.assertEqual(candidate["target_field"], "request_body_json")
            self.assertEqual(candidate["target_locator"], "account_id")
            self.assertEqual(candidate["distinct_app_count"], 3)
            self.assertTrue(candidate["promotion_ready"])
            self.assertEqual(json.loads(output_path.read_text())["promotion_ready_count"], 1)

    def test_missing_history_still_writes_empty_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "missing.jsonl"
            output_path = Path(tmp) / "binding_pattern_candidates.json"

            payload = build_binding_pattern_candidates(history_path, output_path=output_path)

            self.assertEqual(payload["history_row_count"], 0)
            self.assertEqual(payload["candidate_count"], 0)
            self.assertEqual(payload["promotion_ready_count"], 0)
            self.assertEqual(json.loads(output_path.read_text())["candidates"], [])


if __name__ == "__main__":
    unittest.main()

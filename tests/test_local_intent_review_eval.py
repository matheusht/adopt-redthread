from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sanitized_intent_review import build_intent_review, build_intent_review_context
from scripts.evaluate_local_intent_review import evaluate_local_intent_review
from tests.test_sanitized_intent_review import SanitizedIntentReviewTests


class LocalIntentReviewEvalTests(unittest.TestCase):
    def test_eval_reports_fallback_without_local_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = SanitizedIntentReviewTests()._write_batch(root)

            report = evaluate_local_intent_review(batch, root / "eval")

            self.assertEqual(report["schema_version"], "adopt_redthread.local_intent_review_eval.v0")
            self.assertEqual(report["summary"]["case_count"], 1)
            self.assertEqual(report["summary"]["fallback_count"], 1)
            self.assertEqual(report["summary"]["privacy_failure_count"], 0)
            self.assertTrue((root / "eval" / "local_intent_review_eval.md").exists())

    def test_eval_reports_useful_delta_from_valid_local_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = SanitizedIntentReviewTests()._write_batch(root)
            context = build_intent_review_context(batch)
            review = build_intent_review(context)
            review["subjects"][0]["intent_hypotheses"][0]["label"] = "local_eval_delta"
            llm_output = root / "llm_output.json"
            llm_output.write_text(json.dumps(review), encoding="utf-8")

            report = evaluate_local_intent_review(batch, root / "eval", local_llm_cmd=f"cat {llm_output}")

            self.assertEqual(report["summary"]["local_llm_accepted_count"], 1)
            self.assertEqual(report["summary"]["fallback_count"], 0)
            self.assertEqual(report["summary"]["useful_delta_count"], 1)
            self.assertFalse(report["cases"][0]["empty_diff"])


if __name__ == "__main__":
    unittest.main()

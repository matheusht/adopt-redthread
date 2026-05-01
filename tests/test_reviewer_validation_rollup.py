from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_reviewer_validation_rollup import summarize_reviewer_validation_rollup


class ReviewerValidationRollupTests(unittest.TestCase):
    def test_rollup_counts_complete_reviews_without_copying_freeform_answers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_a = root / "summary_a.json"
            summary_b = root / "summary_b.json"
            output = root / "rollup"
            _write_summary(
                summary_a,
                complete=True,
                decision="review",
                behavior_change=True,
                next_probe=True,
                wants_repeat=True,
                unclear="Tenant boundary unclear for raw-reviewer-token-123.",
                probe="Run an ownership boundary probe.",
            )
            _write_summary(
                summary_b,
                complete=False,
                decision="block",
                behavior_change=False,
                next_probe=False,
                wants_repeat=False,
                unclear="Coverage was weak.",
                probe="",
            )

            rollup = summarize_reviewer_validation_rollup([summary_a, summary_b], output_dir=output)
            rollup_json = (output / "reviewer_validation_rollup.json").read_text(encoding="utf-8")
            rollup_md = (output / "reviewer_validation_rollup.md").read_text(encoding="utf-8")

        self.assertEqual(rollup["schema_version"], "adopt_redthread.reviewer_validation_rollup.v1")
        self.assertEqual(rollup["validation_status"], "needs_more_complete_reviews")
        self.assertEqual(rollup["rollup_summary"]["total_summary_count"], 2)
        self.assertEqual(rollup["rollup_summary"]["complete_summary_count"], 1)
        self.assertEqual(rollup["rollup_summary"]["decision_counts"]["review"], 1)
        self.assertEqual(rollup["rollup_summary"]["decision_counts"]["block"], 1)
        self.assertEqual(rollup["rollup_summary"]["behavior_change_count"], 1)
        self.assertEqual(rollup["rollup_summary"]["next_probe_requested_count"], 1)
        self.assertEqual(rollup["theme_summary"]["theme_counts"]["tenant_user_boundary"], 1)
        self.assertEqual(rollup["theme_summary"]["theme_counts"]["coverage_strength"], 1)
        self.assertIn("Run 2 more complete cold reviewer session", rollup_md)
        self.assertIn("Prioritize tenant/user boundary evidence", rollup_md)
        self.assertNotIn("raw-reviewer-token-123", rollup_json)
        self.assertNotIn("raw-reviewer-token-123", rollup_md)

    def test_rollup_privacy_blocks_on_configured_marker_in_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "summary.json"
            _write_summary(
                summary,
                complete=True,
                decision="approve",
                behavior_change=True,
                next_probe=False,
                wants_repeat=True,
                unclear="authorization: leaked by reviewer",
                probe="",
                marker_passed=False,
            )

            with self.assertRaises(RuntimeError):
                summarize_reviewer_validation_rollup([summary], output_dir=root / "rollup")

            rollup = summarize_reviewer_validation_rollup([summary], output_dir=root / "rollup", fail_on_marker_hit=False)

        self.assertEqual(rollup["validation_status"], "privacy_blocked")
        self.assertFalse(rollup["sanitized_marker_audit"]["passed"])
        self.assertEqual(rollup["sanitized_marker_audit"]["marker_hit_count"], 1)

    def test_missing_summary_needs_valid_observation_summaries_not_privacy_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rollup = summarize_reviewer_validation_rollup([root / "missing.json"], output_dir=root / "rollup")

        self.assertEqual(rollup["validation_status"], "needs_valid_observation_summaries")
        self.assertEqual(rollup["rollup_summary"]["missing_or_invalid_file_count"], 1)
        self.assertEqual(rollup["rollup_summary"]["marker_failed_summary_count"], 0)

    def test_three_complete_consistent_reviews_are_ready_for_readout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for index in range(3):
                path = root / f"summary_{index}.json"
                paths.append(path)
                _write_summary(
                    path,
                    complete=True,
                    decision="review",
                    behavior_change=True,
                    next_probe=index == 0,
                    wants_repeat=True,
                    unclear="none recorded",
                    probe="none recorded",
                )

            rollup = summarize_reviewer_validation_rollup(paths, output_dir=root / "rollup")

        self.assertEqual(rollup["validation_status"], "ready_for_validation_readout")
        self.assertEqual(rollup["rollup_summary"]["complete_summary_count"], 3)
        self.assertEqual(rollup["rollup_summary"]["decision_inconsistent_count"], 0)


def _write_summary(
    path: Path,
    *,
    complete: bool,
    decision: str,
    behavior_change: bool,
    next_probe: bool,
    wants_repeat: bool,
    unclear: str,
    probe: str,
    marker_passed: bool = True,
) -> None:
    payload = {
        "schema_version": "adopt_redthread.reviewer_observation_summary.v1",
        "completion_summary": {
            "complete": complete,
            "observation_status": "ready_for_review_signal" if complete else "incomplete_not_reviewer_evidence",
        },
        "validation_signals": {
            "release_decision": decision,
            "decision_consistency": "consistent",
            "behavior_change_recorded": behavior_change,
            "next_probe_requested": next_probe,
            "wants_repeat_review": wants_repeat,
        },
        "confusion_summary": {
            "has_confusion_or_weakness": unclear not in {"", "none recorded"},
            "unclear_or_weak_evidence": unclear,
            "next_probe_requested": probe,
        },
        "sanitized_marker_audit": {
            "passed": marker_passed,
            "marker_hit_count": 0 if marker_passed else 1,
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.summarize_reviewer_observation import summarize_reviewer_observation


FILLED_OBSERVATION = """# Reviewer Observation Template

Use after the reviewer reads the packet artifacts without a walkthrough.

## Review metadata

### reviewer_role
Reviewer role, e.g. security engineer, AI engineer, founder, or buyer.

Answer:
AI engineer

### release_decision
Reviewer decision after reading only the packet artifacts: ship, change, block, or unsure.

Answer:
Change/review before ship.

### trusted_evidence
Evidence that most increased trust.

Answer:
The local gate preserved review semantics and the report separated replay evidence from final bridge decision.

### unclear_or_weak_evidence
Evidence that remained confusing, weak, or missing.

Answer:
The matrix is dense and the RedThread ownership boundary still requires repo knowledge.

### next_probe_requested
Next probe or rerun the reviewer wanted before release.

Answer:
Run an ownership-boundary probe with approved non-production context.

### behavior_change
Did the evidence change a ship/change/block decision, trigger a fix, or trigger a rerun request?

Answer:
It would trigger a rerun before every release touching auth or write scope.

## Silent reviewer answers

### Question 1
Based on this evidence, would you ship, change, or block the release?

Answer:
Review before ship.

### Question 2
What part of the decision did you trust most?

Answer:
The reviewed-write gate semantics.

### Question 3
What part was still unclear or too weak?

Answer:
The RedThread ownership boundary.

### Question 4
Did the attack brief identify the next probe you would run?

Answer:
Yes, rerun auth-boundary probing.

### Question 5
Did the evidence distinguish confirmed issue vs auth/replay failure vs insufficient evidence?

Answer:
Yes, mostly.

### Question 6
Would you want this before every release of this agent/tool?

Answer:
Yes, before every release.
"""


class ReviewerObservationSummaryTests(unittest.TestCase):
    def test_summarizes_filled_observation_without_raw_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observation = root / "reviewer_observation_template.md"
            output = root / "out"
            observation.write_text(FILLED_OBSERVATION, encoding="utf-8")

            summary = summarize_reviewer_observation(observation, output_dir=output, fail_on_marker_hit=True)
            summary_md = (output / "reviewer_observation_summary.md").read_text(encoding="utf-8")

        self.assertEqual(summary["schema_version"], "adopt_redthread.reviewer_observation_summary.v1")
        self.assertTrue(summary["completion_summary"]["complete"])
        self.assertEqual(summary["validation_signals"]["release_decision"], "review")
        self.assertEqual(summary["validation_signals"]["metadata_release_decision"], "review")
        self.assertEqual(summary["validation_signals"]["silent_question_1_decision"], "review")
        self.assertEqual(summary["validation_signals"]["decision_consistency"], "consistent")
        self.assertTrue(summary["validation_signals"]["decision_consistent"])
        self.assertTrue(summary["validation_signals"]["behavior_change_recorded"])
        self.assertTrue(summary["validation_signals"]["next_probe_requested"])
        self.assertTrue(summary["validation_signals"]["wants_repeat_review"])
        self.assertTrue(summary["confusion_summary"]["has_confusion_or_weakness"])
        self.assertTrue(summary["sanitized_marker_audit"]["passed"])
        self.assertIn("# Reviewer Observation Summary", summary_md)
        self.assertIn("Release decision: `review`", summary_md)
        self.assertIn("Decision consistency: `consistent`", summary_md)
        self.assertIn("question_1: Review before ship.", summary_md)
        self.assertIn("Answered silent questions: `6/6`", summary_md)
        self.assertIn("The matrix is dense", summary_md)
        self.assertNotIn("authorization:", summary_md.casefold())

    def test_inline_answer_template_style_is_captured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observation = root / "reviewer_observation_template.md"
            output = root / "out"
            inline = FILLED_OBSERVATION.replace("Answer:\n", "Answer: ")
            observation.write_text(inline, encoding="utf-8")

            summary = summarize_reviewer_observation(observation, output_dir=output, fail_on_marker_hit=True)

        self.assertTrue(summary["completion_summary"]["complete"])
        self.assertEqual(summary["validation_signals"]["release_decision"], "review")
        self.assertEqual(summary["validation_signals"]["decision_consistency"], "consistent")
        self.assertEqual(summary["completion_summary"]["answered_silent_question_count"], 6)

    def test_question_six_yes_counts_as_repeat_review_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            observation = Path(tmp) / "reviewer_observation_template.md"
            text = FILLED_OBSERVATION.replace("Yes, before every release.", "Yes, especially when tool scopes or boundary selectors change before release.")
            observation.write_text(text, encoding="utf-8")

            summary = summarize_reviewer_observation(observation, output_dir=Path(tmp) / "out")

        self.assertTrue(summary["validation_signals"]["wants_repeat_review"])

    def test_incomplete_blank_template_is_not_reviewer_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            observation = Path(tmp) / "reviewer_observation_template.md"
            output = Path(tmp) / "out"
            observation.write_text("# Reviewer Observation Template\n\n### reviewer_role\nAnswer:\n\n", encoding="utf-8")

            summary = summarize_reviewer_observation(observation, output_dir=output)
            summary_md = (output / "reviewer_observation_summary.md").read_text(encoding="utf-8")

        self.assertFalse(summary["completion_summary"]["complete"])
        self.assertEqual(summary["completion_summary"]["observation_status"], "incomplete_not_reviewer_evidence")
        self.assertEqual(summary["validation_signals"]["decision_consistency"], "not_applicable")
        self.assertIn("none_captured_do_not_use_as_validation", summary_md)

    def test_inconsistent_metadata_and_silent_decision_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            observation = Path(tmp) / "reviewer_observation_template.md"
            observation.write_text(FILLED_OBSERVATION.replace("Review before ship.", "Block this release."), encoding="utf-8")

            summary = summarize_reviewer_observation(observation, output_dir=Path(tmp) / "out")

        self.assertEqual(summary["validation_signals"]["metadata_release_decision"], "review")
        self.assertEqual(summary["validation_signals"]["silent_question_1_decision"], "block")
        self.assertEqual(summary["validation_signals"]["decision_consistency"], "inconsistent")
        self.assertFalse(summary["validation_signals"]["decision_consistent"])

    def test_negated_decision_phrases_do_not_become_approve(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            observation = Path(tmp) / "reviewer_observation_template.md"
            negated = FILLED_OBSERVATION.replace("Change/review before ship.", "Cannot approve this yet.").replace("Review before ship.", "Do not ship.")
            observation.write_text(negated, encoding="utf-8")

            summary = summarize_reviewer_observation(observation, output_dir=Path(tmp) / "out")

        self.assertEqual(summary["validation_signals"]["metadata_release_decision"], "review")
        self.assertEqual(summary["validation_signals"]["silent_question_1_decision"], "block")
        self.assertNotEqual(summary["validation_signals"]["release_decision"], "approve")
        self.assertEqual(summary["validation_signals"]["decision_consistency"], "inconsistent")

    def test_marker_audit_fails_observation_with_sensitive_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            observation = Path(tmp) / "reviewer_observation_template.md"
            observation.write_text(FILLED_OBSERVATION + "\nAnswer:\nauthorization: secret\n", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                summarize_reviewer_observation(observation, output_dir=Path(tmp) / "out", fail_on_marker_hit=True)


if __name__ == "__main__":
    unittest.main()

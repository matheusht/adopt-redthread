from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_external_review_handoff import build_external_review_handoff


class ExternalReviewHandoffTests(unittest.TestCase):
    def test_builds_handoff_with_only_sanitized_allowed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "evidence_report.md"
            matrix = root / "evidence_matrix.md"
            packet = root / "reviewer_packet.md"
            template = root / "reviewer_observation_template.md"
            output = root / "handoff"
            report.write_text(
                "# Evidence Report\n"
                "## Reviewer quick read\n"
                "## Silent reviewer checklist\n"
                "## Next evidence to collect\n"
                "## Rerun triggers\n"
                "## Not proven by this run\n",
                encoding="utf-8",
            )
            matrix.write_text(
                "# Evidence Matrix\n"
                "Reviewer action | Finding type | Trusted evidence | Next evidence needed | Rerun triggers\n",
                encoding="utf-8",
            )
            packet.write_text("# Reviewer Evidence Packet\nAllowed artifacts only.\n", encoding="utf-8")
            template.write_text("# Reviewer Observation Template\nAnswer:\n", encoding="utf-8")

            payload = build_external_review_handoff(
                evidence_report=report,
                evidence_matrix=matrix,
                reviewer_packet=packet,
                observation_template=template,
                output_dir=output,
                fail_on_marker_hit=True,
                fail_on_incomplete_handoff=True,
            )
            evidence_report_exists = (output / "evidence_report.md").exists()
            instructions_exists = (output / "external_reviewer_instructions.md").exists()
            instructions = (output / "external_reviewer_instructions.md").read_text(encoding="utf-8")

        self.assertEqual(payload["schema_version"], "adopt_redthread.external_review_handoff.v1")
        self.assertEqual(payload["handoff_status"], "ready_for_external_cold_review")
        self.assertEqual(payload["validation_status"], "not_validation_until_filled_observations_are_summarized")
        self.assertTrue(payload["output_marker_audit"]["passed"])
        self.assertEqual(payload["output_marker_audit"]["marker_hit_count"], 0)
        self.assertTrue(payload["handoff_completeness_audit"]["passed"])
        self.assertIn("external_reviewer_instructions", payload["artifacts"])
        self.assertTrue(evidence_report_exists)
        self.assertTrue(instructions_exists)
        self.assertIn("This is **not** validation by itself", instructions)
        self.assertIn("Give the reviewer only the allowed files", instructions)
        self.assertNotIn("authorization:", instructions.casefold())
        self.assertNotIn("value_preview", instructions.casefold())

    def test_marker_hit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "evidence_report.md"
            matrix = root / "evidence_matrix.md"
            packet = root / "reviewer_packet.md"
            template = root / "reviewer_observation_template.md"
            report.write_text(
                "# Evidence Report\n"
                "## Reviewer quick read\n"
                "## Silent reviewer checklist\n"
                "## Next evidence to collect\n"
                "## Rerun triggers\n"
                "## Not proven by this run\n",
                encoding="utf-8",
            )
            matrix.write_text(
                "# Evidence Matrix\n"
                "Reviewer action | Finding type | Trusted evidence | Next evidence needed | Rerun triggers\n",
                encoding="utf-8",
            )
            packet.write_text("authorization: secret\n", encoding="utf-8")
            template.write_text("# Template\n", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                build_external_review_handoff(
                    evidence_report=report,
                    evidence_matrix=matrix,
                    reviewer_packet=packet,
                    observation_template=template,
                    output_dir=root / "handoff",
                    fail_on_marker_hit=True,
                )


if __name__ == "__main__":
    unittest.main()

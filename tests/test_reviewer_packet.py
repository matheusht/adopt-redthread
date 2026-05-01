from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_reviewer_packet import audit_sanitized_markdown, build_reviewer_packet_from_artifacts


class ReviewerPacketTests(unittest.TestCase):
    def test_packet_points_to_sanitized_artifacts_and_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "evidence_report.md"
            matrix = root / "evidence_matrix.md"
            output = root / "packet"
            report.write_text("# Evidence Report\nNo raw artifact values here.\n", encoding="utf-8")
            matrix.write_text("# Evidence Matrix\napprove review block.\n", encoding="utf-8")

            packet = build_reviewer_packet_from_artifacts(
                evidence_report=report,
                evidence_matrix=matrix,
                output_dir=output,
                fail_on_marker_hit=True,
            )
            packet_md = (output / "reviewer_packet.md").read_text(encoding="utf-8")
            observation_md = (output / "reviewer_observation_template.md").read_text(encoding="utf-8")

        self.assertEqual(packet["schema_version"], "adopt_redthread.reviewer_packet.v1")
        self.assertTrue(packet["sanitized_marker_audit"]["passed"])
        self.assertEqual(packet["sanitized_marker_audit"]["marker_hit_count"], 0)
        self.assertIn("## Open these sanitized artifacts", packet_md)
        self.assertIn("## Sanitized artifact manifest", packet_md)
        self.assertIn("reviewer_observation_template.md", packet_md)
        self.assertIn("Based on this evidence, would you ship, change, or block the release?", packet_md)
        self.assertIn("Did the evidence distinguish confirmed issue vs auth/replay failure vs insufficient evidence?", packet_md)
        self.assertIn("Give the report and matrix to the reviewer first", packet_md)
        self.assertIn("Raw HAR/session/cookie/header/body/run values stay ignored", packet_md)
        self.assertEqual(len(packet["artifact_manifest"]["evidence_report"]["sha256"]), 64)
        self.assertEqual(packet["artifact_manifest"]["evidence_report"]["line_count"], 2)
        self.assertEqual(packet["observation_template"]["schema_version"], "adopt_redthread.reviewer_observation_template.v1")
        self.assertIn("# Reviewer Observation Template", observation_md)
        self.assertIn("### behavior_change", observation_md)
        self.assertIn("Answer:", observation_md)
        self.assertIn("Do not paste raw captured values", observation_md)

    def test_marker_audit_flags_sensitive_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "evidence_report.md"
            report.write_text("authorization: Bearer secret\n", encoding="utf-8")

            audit = audit_sanitized_markdown([report])

        self.assertFalse(audit["passed"])
        self.assertGreaterEqual(audit["marker_hit_count"], 1)
        self.assertIn("authorization:", {hit["marker"] for hit in audit["hits"]})


if __name__ == "__main__":
    unittest.main()

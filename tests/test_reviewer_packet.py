from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_reviewer_packet import audit_handoff_completeness, audit_sanitized_markdown, build_reviewer_packet_from_artifacts


class ReviewerPacketTests(unittest.TestCase):
    def test_packet_points_to_sanitized_artifacts_and_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "evidence_report.md"
            matrix = root / "evidence_matrix.md"
            output = root / "packet"
            report.write_text(
                "# Evidence Report\n"
                "## Reviewer quick read\n"
                "## Silent reviewer checklist\n"
                "## Next evidence to collect\n"
                "## Rerun triggers\n"
                "## Not proven by this run\n"
                "No raw artifact values here.\n",
                encoding="utf-8",
            )
            matrix.write_text(
                "# Evidence Matrix\n"
                "Reviewer action | Finding type | Trusted evidence | Next evidence needed | Rerun triggers\n"
                "approve review block.\n",
                encoding="utf-8",
            )

            packet = build_reviewer_packet_from_artifacts(
                evidence_report=report,
                evidence_matrix=matrix,
                boundary_probe_result=None,
                output_dir=output,
                fail_on_marker_hit=True,
                fail_on_incomplete_handoff=True,
            )
            packet_md = (output / "reviewer_packet.md").read_text(encoding="utf-8")
            observation_md = (output / "reviewer_observation_template.md").read_text(encoding="utf-8")

        self.assertEqual(packet["schema_version"], "adopt_redthread.reviewer_packet.v1")
        self.assertTrue(packet["sanitized_marker_audit"]["passed"])
        self.assertEqual(packet["sanitized_marker_audit"]["marker_hit_count"], 0)
        self.assertTrue(packet["handoff_completeness_audit"]["passed"])
        self.assertEqual(packet["handoff_completeness_audit"]["missing_marker_count"], 0)
        self.assertIn("## Open these sanitized artifacts", packet_md)
        self.assertIn("## Sanitized artifact manifest", packet_md)
        self.assertIn("## Handoff completeness audit", packet_md)
        self.assertIn("## Cold review protocol", packet_md)
        self.assertIn("Allowed artifacts:", packet_md)
        self.assertIn("Forbidden inputs:", packet_md)
        self.assertIn("operator walkthrough before silent answers", packet_md)
        self.assertIn("Observation summary passes the configured sensitive-marker audit", packet_md)
        self.assertIn("reviewer_observation_template.md", packet_md)
        self.assertIn("Boundary probe result: `absent", packet_md)
        self.assertIn("Based on this evidence, would you ship, change, or block the release?", packet_md)
        self.assertIn("Did the evidence distinguish confirmed issue vs auth/replay failure vs insufficient evidence?", packet_md)
        self.assertIn("Give the report, matrix, and boundary result if present to the reviewer first", packet_md)
        self.assertIn("make evidence-observation-summary", packet_md)
        self.assertIn("incomplete_not_reviewer_evidence", packet_md)
        self.assertIn("ship` to `approve`, `change` to `review`, and `block` to `block`", packet_md)
        self.assertIn("Raw HAR/session/cookie/header/body/run values stay ignored", packet_md)
        self.assertEqual(len(packet["artifact_manifest"]["evidence_report"]["sha256"]), 64)
        self.assertEqual(packet["artifact_manifest"]["evidence_report"]["line_count"], 7)
        self.assertEqual(packet["cold_review_protocol"]["allowed_artifacts"], ["evidence_report", "evidence_matrix", "reviewer_packet", "boundary_probe_result_if_present"])
        self.assertIn("raw HAR files", packet["cold_review_protocol"]["forbidden_inputs"])
        self.assertEqual(packet["observation_template"]["schema_version"], "adopt_redthread.reviewer_observation_template.v1")
        self.assertIn("# Reviewer Observation Template", observation_md)
        self.assertIn("### behavior_change", observation_md)
        self.assertIn("Answer:", observation_md)
        self.assertIn("Do not paste raw captured values", observation_md)

    def test_packet_includes_boundary_probe_result_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "evidence_report.md"
            matrix = root / "evidence_matrix.md"
            boundary = root / "tenant_user_boundary_probe_result.md"
            output = root / "packet"
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
            boundary.write_text("# Tenant/User Boundary Probe Result\nResult status: `blocked_missing_context`\n", encoding="utf-8")

            packet = build_reviewer_packet_from_artifacts(
                evidence_report=report,
                evidence_matrix=matrix,
                boundary_probe_result=boundary,
                output_dir=output,
                fail_on_marker_hit=True,
                fail_on_incomplete_handoff=True,
            )
            packet_md = (output / "reviewer_packet.md").read_text(encoding="utf-8")

        self.assertIn("boundary_probe_result", packet["artifacts"])
        self.assertIn("boundary_probe_result", packet["artifact_manifest"])
        self.assertIn("Boundary probe result:", packet_md)
        self.assertIn("tenant_user_boundary_probe_result.md", packet_md)
        self.assertTrue(packet["sanitized_marker_audit"]["passed"])

    def test_handoff_completeness_audit_flags_missing_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "evidence_report.md"
            matrix = Path(tmp) / "evidence_matrix.md"
            report.write_text("# Evidence Report\n## Reviewer quick read\n", encoding="utf-8")
            matrix.write_text("# Evidence Matrix\nReviewer action\n", encoding="utf-8")

            audit = audit_handoff_completeness(report, matrix)

        self.assertFalse(audit["passed"])
        self.assertGreater(audit["missing_marker_count"], 0)
        self.assertIn("evidence_report", {item["artifact"] for item in audit["missing_markers"]})

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

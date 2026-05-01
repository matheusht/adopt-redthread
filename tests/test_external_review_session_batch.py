from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_external_review_session_batch import build_external_review_session_batch


class ExternalReviewSessionBatchTests(unittest.TestCase):
    def test_builds_isolated_sessions_from_sanitized_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = root / "handoff"
            handoff.mkdir()
            _write_handoff(handoff)
            output = root / "sessions"

            batch = build_external_review_session_batch(handoff_dir=handoff, output_dir=output, review_count=2)
            batch_json = (output / "external_review_session_batch.json").read_text(encoding="utf-8")
            batch_md = (output / "external_review_session_batch.md").read_text(encoding="utf-8")

        self.assertEqual(batch["schema_version"], "adopt_redthread.external_review_session_batch.v1")
        self.assertEqual(batch["session_status"], "ready_for_external_reviewer_distribution")
        self.assertEqual(batch["validation_status"], "not_validation_until_filled_observations_are_summarized")
        self.assertEqual(len(batch["sessions"]), 2)
        self.assertTrue(batch["handoff_schema_valid"])
        self.assertTrue(batch["output_marker_audit"]["passed"])
        self.assertIn("review_1", batch_json)
        self.assertIn("make evidence-observation-summary", batch_md)
        self.assertIn("not validation evidence", batch_md)
        self.assertIn("evidence_report.md", batch["sessions"][0]["allowed_artifacts"])

    def test_marker_hit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = root / "handoff"
            handoff.mkdir()
            _write_handoff(handoff)
            (handoff / "evidence_report.md").write_text("authorization: leaked\n", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                build_external_review_session_batch(handoff_dir=handoff, output_dir=root / "sessions", fail_on_marker_hit=True)


def _write_handoff(root: Path) -> None:
    files = {
        "evidence_report.md": "# Evidence report\n\n## Reviewer quick read\nSanitized.\n",
        "evidence_matrix.md": "# Evidence matrix\n\nReviewer action | Finding type | Trusted evidence | Next evidence needed | Rerun triggers\n",
        "reviewer_packet.md": "# Reviewer packet\n\nSanitized.\n",
        "reviewer_observation_template.md": "# Reviewer Observation Template\n\nAnswer:\n",
        "external_reviewer_instructions.md": "# External Human Cold-Review Instructions\n\nAllowed files only.\n",
    }
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    manifest = {
        "schema_version": "adopt_redthread.external_review_handoff.v1",
        "handoff_status": "ready_for_external_cold_review",
        "validation_status": "not_validation_until_filled_observations_are_summarized",
        "protocol": {
            "allowed_artifacts": list(files),
            "forbidden_inputs": ["raw HAR files"],
            "silent_review_required": True,
        },
    }
    (root / "external_review_handoff_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

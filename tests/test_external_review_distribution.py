from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_external_review_distribution_manifest import build_external_review_distribution_manifest


class ExternalReviewDistributionTests(unittest.TestCase):
    def test_builds_ready_distribution_from_fresh_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _write_distribution_inputs(root, freshness_status="fresh")

            payload = build_external_review_distribution_manifest(
                **paths,
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )
            markdown = (root / "out" / "external_review_distribution_manifest.md").read_text(encoding="utf-8")

        self.assertEqual(payload["schema_version"], "adopt_redthread.external_review_distribution_manifest.v1")
        self.assertEqual(payload["distribution_status"], "ready_to_distribute")
        self.assertEqual(len(payload["deliveries"]), 2)
        self.assertEqual(payload["deliveries"][0]["allowed_file_count"], 2)
        self.assertIn("not external validation", " ".join(payload["non_claims"]))
        self.assertIn("review_1", markdown)
        self.assertIn("ready_to_distribute", markdown)

    def test_stale_freshness_blocks_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _write_distribution_inputs(root, freshness_status="stale_or_missing")

            payload = build_external_review_distribution_manifest(
                **paths,
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )

        self.assertEqual(payload["distribution_status"], "stale_or_missing_evidence")
        self.assertIn("stale_or_missing_evidence", {blocker["code"] for blocker in payload["blockers"]})

    def test_marker_hit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _write_distribution_inputs(root, freshness_status="fresh")
            (root / "sessions" / "review_1" / "artifacts" / "evidence_report.md").write_text("authorization: leaked\n", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                build_external_review_distribution_manifest(
                    **paths,
                    output_dir=root / "out",
                    fail_on_marker_hit=True,
                )


def _write_distribution_inputs(root: Path, *, freshness_status: str) -> dict[str, Path]:
    handoff = _write_json(root / "handoff" / "external_review_handoff_manifest.json", {
        "schema_version": "adopt_redthread.external_review_handoff.v1",
        "handoff_status": "ready_for_external_cold_review",
        "validation_status": "not_validation_until_filled_observations_are_summarized",
        "target_review_count": 2,
    })
    session_root = root / "sessions"
    sessions = []
    for index in (1, 2):
        session_dir = session_root / f"review_{index}"
        artifact_dir = session_dir / "artifacts"
        artifact_dir.mkdir(parents=True)
        report = artifact_dir / "evidence_report.md"
        packet = artifact_dir / "reviewer_packet.md"
        filled = session_dir / "filled_reviewer_observation.md"
        report.write_text("# Evidence report\n\nSanitized.\n", encoding="utf-8")
        packet.write_text("# Reviewer packet\n\nSanitized.\n", encoding="utf-8")
        filled.write_text("# Observation\n\nAnswer:\n", encoding="utf-8")
        sessions.append({
            "session_id": f"review_{index}",
            "session_dir": str(session_dir),
            "artifact_dir": str(artifact_dir),
            "allowed_artifacts": {
                "evidence_report.md": _record(report),
                "reviewer_packet.md": _record(packet),
            },
            "filled_observation_path": str(filled),
            "expected_summary_path": str(session_dir / "reviewer_observation_summary.json"),
            "summary_command": f"make evidence-observation-summary OBSERVATION={filled} OBSERVATION_OUTPUT={session_dir}",
        })
    batch = _write_json(session_root / "external_review_session_batch.json", {
        "schema_version": "adopt_redthread.external_review_session_batch.v1",
        "session_status": "ready_for_external_reviewer_distribution",
        "validation_status": "not_validation_until_filled_observations_are_summarized",
        "target_review_count": 2,
        "sessions": sessions,
    })
    freshness = _write_json(root / "freshness" / "evidence_freshness_manifest.json", {
        "schema_version": "adopt_redthread.evidence_freshness_manifest.v1",
        "freshness_status": freshness_status,
        "summary": {"copy_check_count": 4, "problem_count": 0 if freshness_status == "fresh" else 1},
    })
    return {"handoff_manifest": handoff, "session_batch": batch, "freshness_manifest": freshness}


def _record(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "sha256": "test-sha",
        "byte_count": path.stat().st_size,
        "line_count": len(path.read_text(encoding="utf-8").splitlines()),
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()

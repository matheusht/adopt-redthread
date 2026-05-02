from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_evidence_freshness_manifest import build_evidence_freshness_manifest


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    return {
        "path": str(path),
        "sha256": _sha(path),
        "byte_count": len(path.read_bytes()),
        "line_count": len(text.splitlines()),
    }


class EvidenceFreshnessTests(unittest.TestCase):
    def test_builds_fresh_manifest_for_handoff_and_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _write_fixture_tree(root)
            payload = build_evidence_freshness_manifest(
                reviewer_packet=paths["reviewer_packet_json"],
                handoff_manifest=paths["handoff_manifest"],
                session_batch=paths["session_batch"],
                output_dir=root / "out",
                source_artifacts=paths["sources"],
                fail_on_marker_hit=True,
            )

            self.assertEqual(payload["schema_version"], "adopt_redthread.evidence_freshness_manifest.v1")
            self.assertEqual(payload["freshness_status"], "fresh")
            self.assertGreater(payload["summary"]["copy_check_count"], 0)
            self.assertEqual(payload["summary"]["problem_count"], 0)
            self.assertTrue(payload["sanitized_marker_audit"]["passed"])
            self.assertTrue((root / "out" / "evidence_freshness_manifest.md").exists())

    def test_detects_stale_session_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _write_fixture_tree(root)
            (root / "sessions" / "review_1" / "artifacts" / "evidence_report.md").write_text("changed sanitized report\n", encoding="utf-8")

            payload = build_evidence_freshness_manifest(
                reviewer_packet=paths["reviewer_packet_json"],
                handoff_manifest=paths["handoff_manifest"],
                session_batch=paths["session_batch"],
                output_dir=root / "out",
                source_artifacts=paths["sources"],
                fail_on_marker_hit=True,
            )

            self.assertEqual(payload["freshness_status"], "stale_or_missing")
            self.assertGreater(payload["summary"]["problem_count"], 0)
            problem_labels = {item["artifact_label"] for item in payload["summary"]["problem_artifacts"]}
            self.assertIn("evidence_report.md", problem_labels)


def _write_fixture_tree(root: Path) -> dict[str, object]:
    source_dir = root / "source"
    handoff_dir = root / "handoff"
    session_artifact_dir = root / "sessions" / "review_1" / "artifacts"
    source_dir.mkdir(parents=True)
    handoff_dir.mkdir(parents=True)
    session_artifact_dir.mkdir(parents=True)

    source_files = {
        "evidence_report": source_dir / "evidence_report.md",
        "evidence_matrix": source_dir / "evidence_matrix.md",
        "reviewer_packet": source_dir / "reviewer_packet.md",
        "reviewer_observation_template": source_dir / "reviewer_observation_template.md",
        "boundary_probe_result": source_dir / "tenant_user_boundary_probe_result.md",
    }
    for label, path in source_files.items():
        path.write_text(f"# {label}\n\nSanitized reviewer-facing artifact.\n", encoding="utf-8")

    reviewer_packet_json = root / "reviewer_packet.json"
    reviewer_packet_json.write_text(json.dumps({
        "schema_version": "adopt_redthread.reviewer_packet.v1",
        "artifact_manifest": {
            "evidence_report": _record(source_files["evidence_report"]),
            "evidence_matrix": _record(source_files["evidence_matrix"]),
            "boundary_probe_result": _record(source_files["boundary_probe_result"]),
        },
    }), encoding="utf-8")

    handoff_artifacts: dict[str, dict[str, object]] = {}
    for label, source in source_files.items():
        filename = "tenant_user_boundary_probe_result.md" if label == "boundary_probe_result" else f"{label}.md"
        if label == "reviewer_observation_template":
            filename = "reviewer_observation_template.md"
        destination = handoff_dir / filename
        destination.write_bytes(source.read_bytes())
        handoff_label = "boundary_probe_result" if label == "boundary_probe_result" else label
        handoff_artifacts[handoff_label] = _record(destination)
    instructions = handoff_dir / "external_reviewer_instructions.md"
    instructions.write_text("# Instructions\n\nUse only sanitized artifacts.\n", encoding="utf-8")
    handoff_artifacts["external_reviewer_instructions"] = _record(instructions)

    handoff_manifest = root / "external_review_handoff_manifest.json"
    handoff_manifest.write_text(json.dumps({
        "schema_version": "adopt_redthread.external_review_handoff.v1",
        "artifacts": handoff_artifacts,
    }), encoding="utf-8")

    allowed: dict[str, dict[str, object]] = {}
    for entry in handoff_artifacts.values():
        source = Path(str(entry["path"]))
        destination = session_artifact_dir / source.name
        destination.write_bytes(source.read_bytes())
        allowed[source.name] = _record(destination)
    session_batch = root / "external_review_session_batch.json"
    session_batch.write_text(json.dumps({
        "schema_version": "adopt_redthread.external_review_session_batch.v1",
        "sessions": [{
            "session_id": "review_1",
            "allowed_artifacts": allowed,
        }],
    }), encoding="utf-8")

    return {
        "reviewer_packet_json": reviewer_packet_json,
        "handoff_manifest": handoff_manifest,
        "session_batch": session_batch,
        "sources": source_files,
    }


if __name__ == "__main__":
    unittest.main()

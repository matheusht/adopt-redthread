from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_evidence_remediation_queue import build_evidence_remediation_queue


PASS_AUDIT = {"marker_hit_count": 0, "passed": True, "hit_files": []}


class EvidenceRemediationQueueTests(unittest.TestCase):
    def test_builds_queue_from_readiness_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readiness = _write_readiness(root / "readiness.json", marker_hit=False)
            distribution = _write_distribution(root / "distribution.json", status="ready_to_distribute")

            payload = build_evidence_remediation_queue(
                readiness_ledger=readiness,
                distribution_manifest=distribution,
                output_dir=root / "out",
                regenerate_readiness=False,
                fail_on_marker_hit=True,
            )
            markdown = (root / "out" / "evidence_remediation_queue.md").read_text(encoding="utf-8")

        self.assertEqual(payload["schema_version"], "adopt_redthread.evidence_remediation_queue.v1")
        self.assertEqual(payload["queue_status"], "open_items")
        item_ids = [item["id"] for item in payload["items"]]
        self.assertIn("collect_external_reviewer_observations", item_ids)
        self.assertIn("wait_for_approved_boundary_context", item_ids)
        self.assertIn("make evidence-external-validation-readout", payload["commands"])
        self.assertIn("does not change local bridge approve/review/block verdict semantics", " ".join(payload["non_claims"]))
        self.assertIn("collect_external_reviewer_observations", markdown)

    def test_privacy_marker_hit_blocks_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readiness = _write_readiness(root / "readiness.json", marker_hit=True)
            distribution = _write_distribution(root / "distribution.json", status="ready_to_distribute")

            payload = build_evidence_remediation_queue(
                readiness_ledger=readiness,
                distribution_manifest=distribution,
                output_dir=root / "out",
                regenerate_readiness=False,
                fail_on_marker_hit=False,
            )

        self.assertEqual(payload["queue_status"], "privacy_blocked")
        self.assertEqual(payload["items"][0]["id"], "resolve_privacy_marker_hits")

    def test_distribution_not_ready_adds_packaging_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readiness = _write_readiness(root / "readiness.json", marker_hit=False)
            distribution = _write_distribution(root / "distribution.json", status="stale_or_missing_evidence")

            payload = build_evidence_remediation_queue(
                readiness_ledger=readiness,
                distribution_manifest=distribution,
                output_dir=root / "out",
                regenerate_readiness=False,
                fail_on_marker_hit=True,
            )

        self.assertIn("distribution_manifest_not_ready", {item["id"] for item in payload["items"]})


def _write_readiness(path: Path, *, marker_hit: bool) -> Path:
    audit = {"marker_hit_count": 1, "passed": False, "hit_files": ["example"]} if marker_hit else PASS_AUDIT
    payload = {
        "schema_version": "adopt_redthread.evidence_readiness.v1",
        "readiness_status": "waiting_for_external_validation",
        "components": {
            "external_validation_readout": {
                "readout_status": "waiting_for_filled_external_observations",
                "complete_summary_count": 0,
                "target_review_count": 3,
            },
            "boundary_probe_result": {
                "result_status": "blocked_missing_context",
                "boundary_probe_executed": False,
            },
        },
        "blockers": [
            {"code": "external_validation_not_ready", "component": "external_validation_readout", "detail": "waiting_for_filled_external_observations"},
            {"code": "boundary_probe_not_executed", "component": "boundary_probe_result", "detail": "blocked_missing_context"},
        ],
        "marker_audits": [{"label": "test", **audit}],
    }
    return _write_json(path, payload)


def _write_distribution(path: Path, *, status: str) -> Path:
    payload = {
        "schema_version": "adopt_redthread.external_review_distribution_manifest.v1",
        "distribution_status": status,
        "deliveries": [
            {
                "session_id": "review_1",
                "expected_summary_path": "runs/external_review_sessions/review_1/reviewer_observation_summary.json",
                "summary_command": "make evidence-observation-summary OBSERVATION=runs/external_review_sessions/review_1/filled_reviewer_observation.md OBSERVATION_OUTPUT=runs/external_review_sessions/review_1",
            }
        ],
        "input_marker_audit": PASS_AUDIT,
        "output_marker_audit": PASS_AUDIT,
    }
    return _write_json(path, payload)


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()

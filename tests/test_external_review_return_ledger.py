from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_external_review_return_ledger import build_external_review_return_ledger


PASS_AUDIT = {"marker_hit_count": 0, "passed": True, "hit_files": []}


class ExternalReviewReturnLedgerTests(unittest.TestCase):
    def test_waits_for_missing_reviewer_summaries_without_reading_raw_observations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            distribution = _write_distribution(root / "distribution.json", review_count=2)

            payload = build_external_review_return_ledger(
                distribution_manifest=distribution,
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )
            markdown = (root / "out" / "external_review_return_ledger.md").read_text(encoding="utf-8")

        self.assertEqual(payload["schema_version"], "adopt_redthread.external_review_return_ledger.v1")
        self.assertEqual(payload["ledger_status"], "waiting_for_returns")
        self.assertEqual(payload["summary"]["missing_summary_count"], 2)
        self.assertEqual({session["return_status"] for session in payload["sessions"]}, {"missing_summary"})
        self.assertIn("make evidence-observation-summary", payload["commands"][0])
        self.assertIn("waiting_for_returns", markdown)
        self.assertNotIn('"answers"', json.dumps(payload).casefold())

    def test_ready_when_all_expected_summaries_are_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            distribution = _write_distribution(root / "distribution.json", review_count=2, include_boundary_context_request=True)
            for index in (1, 2):
                _write_summary(root / f"review_{index}" / "reviewer_observation_summary.json", complete=True)

            payload = build_external_review_return_ledger(
                distribution_manifest=distribution,
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )

        self.assertEqual(payload["ledger_status"], "ready_for_external_validation_readout")
        self.assertEqual(payload["summary"]["complete_count"], 2)
        self.assertEqual(payload["review_input_coverage"]["boundary_context_request_delivery_status"], "delivered_to_all_sessions")
        self.assertEqual(payload["review_input_coverage"]["delivered_session_count"], 2)
        self.assertFalse(payload["review_input_coverage"]["boundary_context_request_changes_return_status"])
        self.assertTrue(all(session["boundary_context_request_delivered"] for session in payload["sessions"]))
        self.assertEqual(payload["blockers"], [])
        self.assertIn("make evidence-external-validation-readout", payload["commands"])

    def test_missing_context_request_delivery_is_reported_without_changing_waiting_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            distribution = _write_distribution(root / "distribution.json", review_count=2, include_boundary_context_request=False)

            payload = build_external_review_return_ledger(
                distribution_manifest=distribution,
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )
            markdown = (root / "out" / "external_review_return_ledger.md").read_text(encoding="utf-8")

        self.assertEqual(payload["ledger_status"], "waiting_for_returns")
        self.assertEqual(payload["review_input_coverage"]["boundary_context_request_delivery_status"], "not_in_distribution_manifest")
        self.assertEqual(payload["review_input_coverage"]["missing_session_count"], 2)
        self.assertFalse(payload["review_input_coverage"]["boundary_context_request_is_approved_context"])
        self.assertIn("Boundary context request changes return status: `False`", markdown)

    def test_incomplete_and_inconsistent_summaries_need_followup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            distribution = _write_distribution(root / "distribution.json", review_count=2)
            _write_summary(root / "review_1" / "reviewer_observation_summary.json", complete=False)
            _write_summary(
                root / "review_2" / "reviewer_observation_summary.json",
                complete=True,
                decision_consistency="inconsistent",
            )

            payload = build_external_review_return_ledger(
                distribution_manifest=distribution,
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )

        self.assertEqual(payload["ledger_status"], "needs_followup")
        statuses = {session["session_id"]: session["return_status"] for session in payload["sessions"]}
        self.assertEqual(statuses["review_1"], "incomplete_summary")
        self.assertEqual(statuses["review_2"], "needs_decision_followup")
        self.assertIn("incomplete_summary", {blocker["code"] for blocker in payload["blockers"]})

    def test_marker_hit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            distribution = _write_distribution(root / "distribution.json", review_count=1)
            _write_summary(root / "review_1" / "reviewer_observation_summary.json", complete=True, marker_hit=True)

            with self.assertRaises(RuntimeError):
                build_external_review_return_ledger(
                    distribution_manifest=distribution,
                    output_dir=root / "out",
                    fail_on_marker_hit=True,
                )

    def test_invalid_distribution_schema_is_missing_required_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            distribution = _write_json(root / "distribution.json", {"schema_version": "wrong"})

            payload = build_external_review_return_ledger(
                distribution_manifest=distribution,
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )

        self.assertEqual(payload["ledger_status"], "missing_required_evidence")
        self.assertIn("invalid_distribution_schema", {blocker["code"] for blocker in payload["blockers"]})


def _write_distribution(path: Path, *, review_count: int, include_boundary_context_request: bool = False) -> Path:
    deliveries = []
    for index in range(1, review_count + 1):
        session_dir = path.parent / f"review_{index}"
        delivery = {
            "session_id": f"review_{index}",
            "session_dir": str(session_dir),
            "expected_summary_path": str(session_dir / "reviewer_observation_summary.json"),
            "summary_command": f"make evidence-observation-summary OBSERVATION={session_dir / 'filled_reviewer_observation.md'} OBSERVATION_OUTPUT={session_dir}",
        }
        if include_boundary_context_request:
            delivery["allowed_files"] = [
                {
                    "name": "tenant_user_boundary_probe_context_request.md",
                    "path": str(session_dir / "artifacts" / "tenant_user_boundary_probe_context_request.md"),
                    "sha256": "test-sha",
                    "byte_count": 10,
                    "line_count": 1,
                }
            ]
        deliveries.append(delivery)
    return _write_json(path, {
        "schema_version": "adopt_redthread.external_review_distribution_manifest.v1",
        "distribution_status": "ready_to_distribute",
        "target_review_count": review_count,
        "deliveries": deliveries,
        "input_marker_audit": PASS_AUDIT,
        "output_marker_audit": PASS_AUDIT,
    })


def _write_summary(
    path: Path,
    *,
    complete: bool,
    decision_consistency: str = "consistent",
    marker_hit: bool = False,
) -> Path:
    return _write_json(path, {
        "schema_version": "adopt_redthread.reviewer_observation_summary.v1",
        "completion_summary": {
            "complete": complete,
            "missing_field_count": 0 if complete else 1,
            "missing_silent_question_count": 0 if complete else 2,
            "observation_status": "ready_for_review_signal" if complete else "incomplete_not_reviewer_evidence",
        },
        "validation_signals": {
            "release_decision": "review",
            "decision_consistency": decision_consistency,
            "decision_consistent": decision_consistency == "consistent",
            "behavior_change_recorded": complete,
            "next_probe_requested": complete,
            "wants_repeat_review": complete,
        },
        "sanitized_marker_audit": {
            "marker_set": "configured_sensitive_marker_set",
            "marker_count": 6,
            "marker_hit_count": 1 if marker_hit else 0,
            "passed": not marker_hit,
            "hit_sections": ["reviewer_observation"] if marker_hit else [],
        },
    })


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()

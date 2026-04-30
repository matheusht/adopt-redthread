from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_evidence_matrix import build_evidence_matrix


class EvidenceMatrixTests(unittest.TestCase):
    def test_matrix_assigns_approve_review_block_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hero = root / "hero"
            reviewed = root / "reviewed"
            output = root / "matrix"
            victoria_expected = root / "victoria_expected_block.json"
            _make_run(hero, decision="approve", warning=None, blocker=None)
            _make_run(reviewed, decision="review", warning="manual_review_required_for_write_paths", blocker=None)
            _write_json(
                victoria_expected,
                {
                    "reference_id": "victoria-expected-block-v1",
                    "input_file_basename": "victoria_filtered.har",
                    "artifact_policy": "sanitized_expected_only_no_raw_har_or_run_artifacts",
                    "expected": {
                        "fixture_count": 3,
                        "workflow_count": 1,
                        "workflow_class": "reviewed_write_workflow",
                        "declared_response_binding_count": 0,
                        "applied_response_binding_count": 0,
                        "unapplied_response_binding_count": 0,
                        "redthread_replay_passed": True,
                        "gate_decision": "block",
                        "gate_blocker": "live_workflow_blocked_steps_present",
                        "workflow_reason": "missing_write_context",
                        "redthread_control_detail": "authorization deny matched expected deny",
                    },
                },
            )

            matrix = build_evidence_matrix(
                output_dir=output,
                hero_run_dir=hero,
                reviewed_run_dir=reviewed,
                victoria_run_dir=root / "missing_victoria_run",
                victoria_expected=victoria_expected,
                regenerate=False,
            )

            decisions = [row["gate_decision"] for row in matrix["rows"]]
            agents = [row["decision_agent"] for row in matrix["rows"]]
            matrix_md = (output / "evidence_matrix.md").read_text()

        self.assertEqual(decisions, ["approve", "review", "block"])
        self.assertEqual(agents, ["ReleaseApprovalAgent", "SecurityReviewAgent", "SafetyBlockAgent"])
        self.assertIn("Victoria HAR block example", matrix_md)
        self.assertIn("live_workflow_blocked_steps_present / missing_write_context", matrix_md)


def _make_run(path: Path, *, decision: str, warning: str | None, blocker: str | None) -> None:
    path.mkdir()
    warnings = [warning] if warning else []
    blockers = [blocker] if blocker else []
    _write_json(
        path / "workflow_summary.json",
        {
            "input_file": "fixture.har",
            "fixture_count": 2,
            "live_workflow_count": 1,
            "live_workflow_requirement_summary": {"workflow_class_counts": {"safe_read_workflow": 1}},
            "live_workflow_binding_application_summary": {
                "planned_response_binding_count": 1,
                "applied_response_binding_count": 1,
                "unapplied_response_binding_count": 0,
            },
            "redthread_replay_passed": True,
            "gate_decision": decision,
        },
    )
    _write_json(path / "gate_verdict.json", {"decision": decision, "warnings": warnings, "blockers": blockers})
    _write_json(path / "live_workflow_replay.json", {"workflow_count": 1, "reason_counts": {}})
    _write_json(path / "redthread_replay_verdict.json", {"passed": True})
    _write_json(
        path / "redthread_runtime_inputs.json",
        {
            "redthread_replay_bundle": {
                "traces": [
                    {
                        "authorization_decision": {"decision": "allow"},
                        "expected_authorization": "allow",
                    }
                ]
            }
        },
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()

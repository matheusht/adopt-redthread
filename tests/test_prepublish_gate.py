from __future__ import annotations

import unittest

from adapters.zapi.loader import build_fixture_bundle
from scripts.generate_replay_pack import build_replay_pack
from scripts.prepublish_gate import build_gate_verdict


class PrepublishGateTests(unittest.TestCase):
    def test_prepublish_gate_blocks_when_sandbox_only_items_exist(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_discovery.json")
        replay_pack = build_replay_pack(bundle)

        verdict = build_gate_verdict(replay_pack, allow_sandbox_only=False)

        self.assertEqual(verdict["decision"], "block")
        self.assertIn("sandbox_only_items_present", verdict["blockers"])
        self.assertIn("manual_review_required_for_write_paths", verdict["warnings"])

    def test_prepublish_gate_can_downgrade_to_review_when_sandbox_items_are_allowed(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_discovery.json")
        replay_pack = build_replay_pack(bundle)

        verdict = build_gate_verdict(replay_pack, allow_sandbox_only=True)

        self.assertEqual(verdict["decision"], "review")
        self.assertEqual(verdict["blockers"], [])
        self.assertIn("manual_review_required_for_write_paths", verdict["warnings"])

    def test_prepublish_gate_blocks_when_live_evidence_shows_failures(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_filtered_har.json")
        replay_pack = build_replay_pack(bundle)

        verdict = build_gate_verdict(
            replay_pack,
            allow_sandbox_only=True,
            live_safe_replay={
                "allowed_case_count": 1,
                "executed_case_count": 1,
                "success_count": 0,
            },
            live_workflow_replay={
                "workflow_count": 1,
                "executed_workflow_count": 1,
                "successful_workflow_count": 0,
                "blocked_workflow_count": 0,
                "aborted_workflow_count": 1,
                "reason_counts": {"http_status_401": 1},
                "results": [{"status": "aborted", "failure_reason_code": "http_status_401"}],
            },
            redthread_replay_verdict={"passed": False},
        )

        self.assertEqual(verdict["decision"], "block")
        self.assertIn("live_safe_replay_failures_present", verdict["blockers"])
        self.assertIn("live_workflow_replay_failures_present", verdict["blockers"])
        self.assertIn("live_workflow_runtime_failures_present", verdict["blockers"])
        self.assertIn("redthread_replay_verdict_failed", verdict["blockers"])
        self.assertEqual(verdict["evidence_summary"]["redthread_replay_verdict"], {"passed": False})

    def test_prepublish_gate_warns_when_live_evidence_expected_but_missing_execution(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_filtered_har.json")
        replay_pack = build_replay_pack(bundle)

        verdict = build_gate_verdict(
            replay_pack,
            allow_sandbox_only=True,
            live_safe_replay={
                "allowed_case_count": 2,
                "executed_case_count": 0,
                "success_count": 0,
            },
            live_workflow_replay={
                "workflow_count": 1,
                "executed_workflow_count": 0,
                "successful_workflow_count": 0,
                "blocked_workflow_count": 1,
                "aborted_workflow_count": 0,
                "reason_counts": {"step_not_executable": 1},
                "results": [],
            },
            redthread_replay_verdict={"passed": True},
        )

        self.assertEqual(verdict["decision"], "block")
        self.assertIn("live_safe_replay_not_executed", verdict["warnings"])
        self.assertIn("live_workflow_replay_not_executed", verdict["warnings"])
        self.assertIn("live_workflow_review_gap_present", verdict["warnings"])
        self.assertIn("live_workflow_blocked_steps_present", verdict["blockers"])
        self.assertNotIn("redthread_replay_verdict_failed", verdict["blockers"])


if __name__ == "__main__":
    unittest.main()

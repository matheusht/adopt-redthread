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
                "reason_counts": {"missing_auth_context": 1},
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

    def test_prepublish_gate_blocks_on_workflow_context_mismatch(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_filtered_har.json")
        replay_pack = build_replay_pack(bundle)

        verdict = build_gate_verdict(
            replay_pack,
            allow_sandbox_only=True,
            live_workflow_replay={
                "workflow_count": 1,
                "executed_workflow_count": 0,
                "successful_workflow_count": 0,
                "blocked_workflow_count": 1,
                "aborted_workflow_count": 0,
                "reason_counts": {"host_continuity_mismatch": 1},
                "results": [],
            },
            redthread_replay_verdict={"passed": True},
        )

        self.assertEqual(verdict["decision"], "block")
        self.assertIn("live_workflow_context_mismatch_present", verdict["blockers"])

    def test_prepublish_gate_surfaces_workflow_requirement_summary(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_filtered_har.json")
        replay_pack = build_replay_pack(bundle)

        verdict = build_gate_verdict(
            replay_pack,
            allow_sandbox_only=True,
            live_workflow_replay={
                "workflow_count": 1,
                "executed_workflow_count": 1,
                "successful_workflow_count": 1,
                "blocked_workflow_count": 0,
                "aborted_workflow_count": 0,
                "reason_counts": {},
                "workflow_requirement_summary": {
                    "workflow_class_counts": {"auth_safe_read_workflow": 1},
                    "same_host_continuity_required_count": 1,
                    "same_target_env_required_count": 1,
                    "shared_auth_context_required_count": 1,
                    "same_auth_context_required_count": 1,
                    "approved_auth_context_required_count": 1,
                    "shared_write_context_required_count": 0,
                    "same_write_context_required_count": 0,
                    "approved_write_context_required_count": 0,
                    "auth_header_contract_required_count": 1,
                    "declared_response_binding_count": 2,
                    "applied_response_binding_count": 1,
                    "inferred_response_binding_count": 1,
                    "approved_response_binding_count": 1,
                    "pending_review_response_binding_count": 0,
                    "rejected_response_binding_count": 0,
                    "replaced_response_binding_count": 1,
                    "required_header_family_counts": {"auth": 1},
                    "context_contract_failure_counts": {},
                    "failure_class_counts": {},
                },
                "workflow_failure_class_summary": {"review_gap": 1},
                "results": [],
            },
            redthread_replay_verdict={"passed": True},
            workflow_plan={
                "approved_binding_alias_count": 1,
                "approved_binding_alias_summary": {
                    "used_alias_count": 1,
                    "used_workflow_count": 1,
                    "used_aliases": [{"target_path": "profileKey"}],
                },
            },
        )

        self.assertEqual(
            verdict["evidence_summary"]["live_workflow_replay"]["workflow_requirement_summary"]["workflow_class_counts"],
            {"auth_safe_read_workflow": 1},
        )
        self.assertIn("live_workflow_classes=auth_safe_read_workflow:1", verdict["notes"])
        self.assertIn("live_workflow_same_target_env_required_count=1", verdict["notes"])
        self.assertIn("live_workflow_same_auth_context_required_count=1", verdict["notes"])
        self.assertIn("live_workflow_approved_auth_context_required_count=1", verdict["notes"])
        self.assertIn("live_workflow_auth_header_contract_required_count=1", verdict["notes"])
        self.assertIn("live_workflow_declared_response_binding_count=2", verdict["notes"])
        self.assertIn("live_workflow_applied_response_binding_count=1", verdict["notes"])
        self.assertIn("live_workflow_inferred_response_binding_count=1", verdict["notes"])
        self.assertIn("live_workflow_approved_response_binding_count=1", verdict["notes"])
        self.assertIn("live_workflow_pending_review_response_binding_count=0", verdict["notes"])
        self.assertIn("live_workflow_rejected_response_binding_count=0", verdict["notes"])
        self.assertIn("live_workflow_replaced_response_binding_count=1", verdict["notes"])
        self.assertIn("live_workflow_required_header_families=auth:1", verdict["notes"])
        self.assertIn("live_workflow_context_contract_failures=none", verdict["notes"])
        self.assertIn("live_workflow_failure_classes=review_gap:1", verdict["notes"])
        self.assertIn("live_workflow_approved_binding_alias_count=1", verdict["notes"])
        self.assertIn("live_workflow_approved_binding_alias_used_count=1", verdict["notes"])
        self.assertIn("live_workflow_approved_binding_alias_targets=profileKey", verdict["notes"])


if __name__ == "__main__":
    unittest.main()

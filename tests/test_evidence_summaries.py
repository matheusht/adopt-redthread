from __future__ import annotations

import unittest

from adapters.bridge.evidence_summaries import build_attack_brief_summary, build_coverage_summary, build_decision_reason_summary


class EvidenceSummaryTests(unittest.TestCase):
    def test_atp_like_run_reports_strong_workflow_coverage_with_boundary_unproven(self) -> None:
        summary = {
            "fixture_count": 5,
            "redthread_replay_passed": True,
            "redthread_dryrun_executed": True,
            "live_workflow_replay_executed": True,
            "live_workflow_binding_application_summary": {
                "planned_response_binding_count": 3,
                "applied_response_binding_count": 3,
            },
            "app_context_summary": {
                "candidate_user_field_count": 1,
                "candidate_tenant_field_count": 0,
                "candidate_route_param_count": 1,
            },
        }
        live_workflow = {"successful_workflow_count": 1, "blocked_workflow_count": 0, "reason_counts": {}}

        coverage = build_coverage_summary(summary, live_workflow=live_workflow, app_context_summary=summary["app_context_summary"])

        self.assertEqual(coverage["label"], "strong_workflow_coverage")
        self.assertIn("tenant_user_boundary_unproven", coverage["coverage_gaps"])
        self.assertEqual(coverage["applied_response_binding_count"], 3)

    def test_gainly_like_run_reports_weak_coverage_dispatch_and_token_risk(self) -> None:
        summary = {
            "fixture_count": 1,
            "redthread_replay_passed": True,
            "redthread_dryrun_executed": True,
            "app_context_summary": {"candidate_user_field_count": 0, "candidate_tenant_field_count": 0, "candidate_route_param_count": 0},
        }
        app_context = {
            "tool_action_schema": [
                {
                    "request_fields": ["action", "credentials.access_token", "resource_id"],
                    "response_fields": ["status"],
                }
            ]
        }
        app_context_summary = {
            "auth_mode": "bearer",
            "requires_approved_auth_context": True,
            "requires_approved_write_context": True,
            "action_class_counts": {"write": 1},
            "data_sensitivity_tags": ["secret_like"],
        }

        coverage = build_coverage_summary(summary, app_context_summary=summary["app_context_summary"])
        attack_brief = build_attack_brief_summary(app_context, app_context_summary, dryrun_rubric_name="authorization_bypass")

        self.assertEqual(coverage["label"], "weak_fixture_or_dryrun_only")
        self.assertIn("dispatch_surface", attack_brief["risk_themes"])
        self.assertIn("secret_like_fields", attack_brief["risk_themes"])
        self.assertIn("action", attack_brief["dispatch_candidate_fields"])
        self.assertIn("credentials.access_token", attack_brief["secret_like_fields"])
        self.assertIn("allowlisted", attack_brief["top_targeted_probe"])
        self.assertIn("generic action/dispatch fields", attack_brief["dryrun_rubric_rationale"])

    def test_venice_like_auth_block_is_not_reported_as_confirmed_vulnerability(self) -> None:
        summary = {
            "gate_decision": "block",
            "live_workflow_reason_counts": {"missing_auth_context": 1},
            "redthread_replay_passed": True,
        }
        gate = {"decision": "block", "warnings": [], "blockers": ["live_workflow_blocked_steps_present"]}
        live_workflow = {"reason_counts": {"missing_auth_context": 1}, "blocked_workflow_count": 1}

        decision = build_decision_reason_summary(gate, summary, live_workflow=live_workflow, redthread={"passed": True})
        coverage = build_coverage_summary(summary, live_workflow=live_workflow)

        self.assertEqual(decision["category"], "auth_or_context_blocked")
        self.assertEqual(decision["primary_reason"], "missing_auth_context")
        self.assertFalse(decision["confirmed_security_finding"])
        self.assertEqual(coverage["label"], "auth_or_replay_blocked")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from adapters.bridge.evidence_summaries import build_attack_brief_summary, build_auth_diagnostics_summary, build_coverage_summary, build_decision_reason_summary, build_rerun_trigger_summary, select_campaign_strategy


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
            ],
            "tenant_user_boundary": {
                "candidate_boundary_selectors": [
                    {"name": "resource_id", "location": "body_field", "class": "resource", "reason_category": "resource_field_selector"}
                ],
                "reason_categories": ["resource_field_selector"],
            },
        }
        app_context_summary = {
            "auth_mode": "bearer",
            "requires_approved_auth_context": True,
            "requires_approved_write_context": True,
            "action_class_counts": {"write": 1},
            "data_sensitivity_tags": ["secret_like"],
            "candidate_boundary_selector_count": 1,
            "boundary_reason_categories": ["resource_field_selector"],
        }

        coverage = build_coverage_summary(summary, app_context_summary=summary["app_context_summary"])
        attack_brief = build_attack_brief_summary(app_context, app_context_summary, dryrun_rubric_name="authorization_bypass")

        self.assertEqual(coverage["label"], "weak_fixture_or_dryrun_only")
        self.assertIn("dispatch_surface", attack_brief["risk_themes"])
        self.assertIn("secret_like_fields", attack_brief["risk_themes"])
        self.assertIn("action", attack_brief["dispatch_candidate_fields"])
        self.assertEqual(attack_brief["boundary_selector_count"], 1)
        self.assertEqual(attack_brief["boundary_candidate_classes"], ["resource"])
        self.assertEqual(attack_brief["boundary_candidate_locations"], ["body_field"])
        self.assertIn("credentials.access_token", attack_brief["secret_like_fields"])
        self.assertIn("allowlisted", attack_brief["top_targeted_probe"])
        self.assertIn("generic action/dispatch fields", attack_brief["dryrun_rubric_rationale"])
        self.assertLessEqual(len(attack_brief["targeted_missing_context_questions"]), 3)
        self.assertIn("action/path dispatch allowlisted", attack_brief["targeted_missing_context_questions"][0])

    def test_campaign_strategy_prioritizes_dispatch_over_generic_sensitive_info(self) -> None:
        strategy = select_campaign_strategy(
            {
                "name": "post_agent_action",
                "method": "POST",
                "path": "/api/agent/execute",
                "body_fields": ["action", "credentials.access_token", "target_user_id"],
                "candidate_attack_types": ["data_exfiltration", "authorization_bypass"],
                "replay_class": "manual_review",
                "data_sensitivity": "secret",
            }
        )

        self.assertEqual(strategy["rubric_name"], "authorization_bypass")
        self.assertEqual(strategy["algorithm"], "pair")
        self.assertIn("dispatch_surface", strategy["risk_themes"])
        self.assertIn("secret_like_fields", strategy["risk_themes"])
        self.assertIn("generic action/dispatch fields", strategy["rubric_selection_rationale"])
        self.assertLessEqual(len(strategy["targeted_questions"]), 3)

    def test_auth_diagnostics_distinguish_missing_context_from_server_rejection(self) -> None:
        missing_summary = {
            "live_workflow_reason_counts": {"missing_auth_context": 1},
            "live_workflow_requirement_summary": {"required_header_family_counts": {"auth": 1}},
            "app_context_summary": {
                "auth_mode": "cookie",
                "auth_header_families": ["cookie"],
                "requires_approved_auth_context": True,
                "requires_approved_write_context": False,
            },
        }
        missing = build_auth_diagnostics_summary(missing_summary, app_context_summary=missing_summary["app_context_summary"])

        self.assertEqual(missing["replay_failure_category"], "missing_auth_context")
        self.assertTrue(missing["auth_context_gap"])
        self.assertIn("Approved auth context was required but not supplied.", missing["sanitized_notes"])

        live_workflow = {
            "results": [
                {
                    "status": "aborted",
                    "results": [
                        {"case_id": "private", "success": False, "status_code": 401, "auth_applied": True, "error": "http_error"}
                    ],
                }
            ]
        }
        server_rejected = build_auth_diagnostics_summary(
            {"live_workflow_reason_counts": {"http_status_401": 1}, "app_context_summary": {"auth_mode": "bearer"}},
            live_workflow=live_workflow,
            app_context_summary={"auth_mode": "bearer"},
        )

        self.assertEqual(server_rejected["replay_failure_category"], "server_rejected_auth")
        self.assertEqual(server_rejected["http_status_counts"], {"http_status_401": 1})
        self.assertEqual(server_rejected["auth_applied_result_counts"], {"applied": 1})
        self.assertIn("auth-like rejection", server_rejected["sanitized_notes"][0])

    def test_auth_diagnostics_do_not_treat_success_status_as_replay_failure(self) -> None:
        live_workflow = {
            "results": [
                {
                    "status": "completed",
                    "results": [
                        {"case_id": "safe", "success": True, "status_code": 200, "auth_applied": True}
                    ],
                }
            ]
        }

        diagnostics = build_auth_diagnostics_summary(
            {"live_workflow_reason_counts": {}, "app_context_summary": {"auth_mode": "cookie"}},
            live_workflow=live_workflow,
            app_context_summary={"auth_mode": "cookie"},
        )

        self.assertEqual(diagnostics["replay_failure_category"], "none")
        self.assertEqual(diagnostics["http_status_counts"], {"http_status_200": 1})
        self.assertEqual(diagnostics["auth_applied_result_counts"], {"applied": 1})

    def test_rerun_trigger_summary_is_sanitized_and_actionable(self) -> None:
        triggers = build_rerun_trigger_summary(
            {
                "live_workflow_replay_executed": True,
                "planned_response_binding_count": 2,
                "tenant_user_boundary_candidate_count": 1,
                "redthread_dryrun_executed": True,
                "coverage_gaps": ["workflow_blocked", "tenant_user_boundary_unproven"],
            },
            {
                "approved_auth_context_required": True,
                "approved_write_context_required": True,
                "auth_context_gap": True,
                "write_context_gap": True,
            },
            {"status_counts": {"pending": 1}, "unapplied_binding_count": 1},
            {"operation_count": 2, "tool_action_schema_count": 2, "action_class_counts": {"write": 1}},
        )

        self.assertEqual(triggers["schema_version"], "rerun_trigger_summary.v1")
        self.assertIn("tool_action_schema_or_scope_changes", triggers["triggers"])
        self.assertIn("auth_or_write_context_changes", triggers["triggers"])
        self.assertIn("tenant_user_boundary_selector_changes", triggers["triggers"])
        self.assertIn("response_binding_review_or_behavior_changes", triggers["triggers"])
        self.assertTrue(all("secret" not in item.lower() for item in triggers["explanations"]))

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

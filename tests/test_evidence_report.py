from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_evidence_report import build_evidence_report


class EvidenceReportTests(unittest.TestCase):
    def test_block_report_names_exact_workflow_blocker_plainly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "victoria"
            run_dir.mkdir()
            _write_json(
                run_dir / "workflow_summary.json",
                {
                    "ingestion": "zapi",
                    "input_file": "victoria_filtered.har",
                    "fixture_count": 3,
                    "live_workflow_count": 1,
                    "live_workflow_replay_executed": True,
                    "live_workflow_reason_counts": {"missing_write_context": 1},
                    "live_workflow_requirement_summary": {"workflow_class_counts": {"reviewed_write_workflow": 1}},
                    "live_workflow_failure_class_summary": {"review_gap": 1},
                    "live_workflow_binding_application_summary": {
                        "planned_response_binding_count": 1,
                        "applied_response_binding_count": 1,
                        "unapplied_response_binding_count": 0,
                        "binding_application_failure_counts": {},
                    },
                    "live_workflow_binding_audit_summary": {
                        "schema_version": "binding_audit_summary.v1",
                        "planned_binding_count": 1,
                        "applied_binding_count": 1,
                        "unapplied_binding_count": 0,
                        "status_counts": {"approved": 1},
                        "origin_counts": {"inferred": 1},
                        "target_field_counts": {"request_body_json": 1},
                        "changed_later_request_count": 1,
                        "audit_records": [
                            {
                                "binding_id": "user_id",
                                "origin": "inferred",
                                "review_status": "approved",
                                "target_field": "request_body_json",
                                "applied_at_runtime": True,
                                "allow_or_hold_reason": "approved_binding_applied",
                            }
                        ],
                    },
                    "redthread_replay_passed": True,
                    "redthread_dryrun_executed": True,
                    "decision_reason_summary": {
                        "decision": "block",
                        "category": "auth_or_context_blocked",
                        "primary_reason": "missing_write_context",
                        "confirmed_security_finding": False,
                        "explanation": "Required approved auth or write context was missing or mismatched, so this is not a confirmed security finding.",
                    },
                    "coverage_summary": {
                        "label": "auth_or_replay_blocked",
                        "live_safe_replay_executed": False,
                        "live_workflow_replay_executed": True,
                        "successful_workflow_count": 0,
                        "blocked_workflow_count": 1,
                        "planned_response_binding_count": 0,
                        "applied_response_binding_count": 0,
                        "tenant_user_boundary_probed": False,
                        "coverage_gaps": ["auth_or_replay_blocked", "tenant_user_boundary_unproven", "workflow_blocked"],
                    },
                    "auth_diagnostics_summary": {
                        "auth_mode": "cookie",
                        "auth_header_families": ["cookie"],
                        "required_header_family_counts": {"auth": 1},
                        "approved_auth_context_required": True,
                        "approved_auth_context_supplied": False,
                        "approved_write_context_required": True,
                        "approved_write_context_supplied": False,
                        "auth_applied_result_counts": {},
                        "http_status_counts": {},
                        "replay_failure_category": "missing_write_context",
                        "sanitized_notes": ["Approved write context was required but not supplied."],
                    },
                    "attack_brief_summary": {
                        "risk_themes": ["tenant_user_boundary", "write_surface"],
                        "top_targeted_probe": "Verify user/tenant identifiers are server-side derived or ownership-checked, not trusted from the client.",
                        "targeted_missing_context_questions": ["Can this actor access another actor's object with this identifier class?"],
                        "boundary_candidate_fields": ["user_id"],
                        "boundary_candidate_classes": ["user"],
                        "boundary_candidate_locations": ["body_field"],
                        "dispatch_candidate_fields": [],
                        "secret_like_fields": [],
                        "dryrun_rubric_rationale": "Selected because user/tenant/resource identifiers need ownership-boundary probing.",
                    },
                    "app_context_summary": {
                        "schema_version": "app_context.v1",
                        "operation_count": 3,
                        "tool_action_schema_count": 3,
                        "action_class_counts": {"read": 1, "write": 2},
                        "auth_mode": "cookie",
                        "auth_scope_hints": ["user_scoped"],
                        "requires_approved_context": True,
                        "requires_approved_auth_context": True,
                        "requires_approved_write_context": True,
                        "data_sensitivity_tags": ["support_message_like", "user_data"],
                        "candidate_user_field_count": 1,
                        "candidate_tenant_field_count": 0,
                        "candidate_resource_field_count": 0,
                        "candidate_route_param_count": 0,
                        "candidate_boundary_selector_count": 1,
                        "boundary_reason_categories": ["user_field_selector"],
                    },
                    "gate_decision": "block",
                },
            )
            _write_json(
                run_dir / "gate_verdict.json",
                {
                    "decision": "block",
                    "warnings": ["manual_review_required_for_write_paths", "live_workflow_review_gap_present"],
                    "blockers": ["live_workflow_blocked_steps_present"],
                },
            )
            _write_json(
                run_dir / "live_workflow_replay.json",
                {
                    "successful_workflow_count": 0,
                    "blocked_workflow_count": 1,
                    "aborted_workflow_count": 0,
                    "reason_counts": {"missing_write_context": 1},
                },
            )
            _write_json(run_dir / "redthread_replay_verdict.json", {"passed": True})

            report = build_evidence_report(run_dir)

        self.assertIn("## Reviewer quick read", report)
        self.assertIn("Tested input: `victoria_filtered.har` via `zapi` with `3` fixtures", report)
        self.assertIn("Workflow exercised: Live workflow replay executed with `0` successful, `1` blocked", report)
        self.assertIn("bindings_applied_planned=`1/1`", report)
        self.assertIn("Local gate outcome: `block`; category=`auth_or_context_blocked`; confirmed_security_finding=`False`", report)
        self.assertIn("Still not proven: auth_or_replay_blocked,tenant_user_boundary_unproven,workflow_blocked", report)
        self.assertIn("Next useful probe: Verify user/tenant identifiers", report)
        self.assertIn("RedThread replay/dry-run is evidence", report)
        self.assertIn("Local bridge gate decision", report)
        self.assertIn("Exact decision reason", report)
        self.assertIn("Decision reason category: `auth_or_context_blocked`", report)
        self.assertIn("Confirmed security finding: `False`", report)
        self.assertIn("missing_write_context:1", report)
        self.assertIn("Approved staging write context was required but was not supplied", report)
        self.assertIn("## App context for RedThread", report)
        self.assertIn("Context schema: `app_context.v1`", report)
        self.assertIn("Action classes: `read:1,write:2`", report)
        self.assertIn("Auth mode observed from structural hints: `cookie`", report)
        self.assertIn("Approved auth context required: `True`", report)
        self.assertIn("Approved write context required: `True`", report)
        self.assertIn("Sensitivity tags: `support_message_like,user_data`", report)
        self.assertIn("Candidate resource fields: `0`", report)
        self.assertIn("Boundary selectors: `1`", report)
        self.assertIn("Boundary reason categories: `user_field_selector`", report)
        self.assertIn("## Coverage confidence", report)
        self.assertIn("Coverage label: `auth_or_replay_blocked`", report)
        self.assertIn("Coverage gaps: `auth_or_replay_blocked,tenant_user_boundary_unproven,workflow_blocked`", report)
        self.assertIn("## Auth delivery diagnostics", report)
        self.assertIn("Auth header families: `cookie`", report)
        self.assertIn("Required header family counts: `auth:1`", report)
        self.assertIn("Approved auth context required/supplied: `True/False`", report)
        self.assertIn("Replay/auth failure category: `missing_write_context`", report)
        self.assertIn("Approved write context was required but not supplied", report)
        self.assertIn("## Attack brief for RedThread", report)
        self.assertIn("Top targeted probe/question: Verify user/tenant identifiers", report)
        self.assertIn("Targeted missing-context questions: `Can this actor access another actor's object", report)
        self.assertIn("Boundary candidate classes: `user`", report)
        self.assertIn("Boundary candidate locations: `body_field`", report)
        self.assertIn("Dry-run rubric rationale: Selected because user/tenant/resource identifiers", report)
        self.assertIn("Binding audit schema: `binding_audit_summary.v1`", report)
        self.assertIn("Binding audit statuses: `approved:1`", report)
        self.assertIn("Binding origins: `inferred:1`", report)
        self.assertIn("Binding target classes: `request_body_json:1`", report)
        self.assertIn("Bindings that changed later requests structurally: `1`", report)
        self.assertIn("user_id:inferred/approved->applied:True", report)
        self.assertIn("## Not proven by this run", report)
        self.assertIn("successful execution of the blocked workflow under approved context", report)
        self.assertIn("cross-user, cross-tenant, or resource-ownership enforcement", report)
        self.assertIn("valid auth/session/write-context delivery for this run; this is not proof of a confirmed vulnerability", report)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.live_replay.approved_context_replay import SCHEMA_APPROVAL_VERSION, approved_context_replay, build_execution_approval_request


class ApprovedContextReplayTests(unittest.TestCase):
    def test_default_mode_writes_not_run_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attack = root / "live_attack_plan.json"
            _write_json(attack, _attack_plan())

            result = approved_context_replay(
                attack,
                case_id="get_api_Profile",
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )
            markdown = (root / "out" / "approved_context_replay.md").read_text(encoding="utf-8")
            plan = json.loads((root / "out" / "approved_context_replay_plan.json").read_text(encoding="utf-8"))

        self.assertEqual(result["schema_version"], "adopt_redthread.approved_context_replay_result.v1")
        self.assertEqual(plan["schema_version"], "adopt_redthread.approved_context_replay_plan.v1")
        self.assertEqual(result["result_class"], "not_run")
        self.assertFalse(result["execution_state"]["executed"])
        self.assertFalse(result["execution_state"]["execution_approved"])
        self.assertIn("execution_not_requested", result["blocked_reasons"])
        self.assertFalse(result["release_gate_override"])
        self.assertFalse(result["confirmed_security_finding"])
        self.assertFalse(result["approval_scope"]["approval_supplied"])
        self.assertFalse(result["approval_scope"]["explicit_case_scope_present"])
        self.assertFalse(result["approval_scope"]["raw_approval_values_persisted"])
        self.assertTrue(result["output_marker_audit"]["passed"])
        self.assertIn("# Approved Context Replay v1", markdown)
        self.assertIn("`context_ready` is not execution proof", markdown)
        self.assertEqual(result["case_evidence"]["body_field_count"], 0)
        self.assertNotIn("authorization:", markdown.casefold())
        self.assertNotIn("value_preview", json.dumps(result).casefold())

    def test_approved_write_context_can_be_ready_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attack = root / "live_attack_plan.json"
            write_context = root / "write_context.json"
            approval = root / "approval.json"
            _write_json(attack, _attack_plan())
            _write_json(write_context, _write_context())
            _write_json(approval, _approval("post_api_Users", ["live_reviewed_write_staging"]))

            result = approved_context_replay(
                attack,
                case_id="post_api_Users",
                write_context=write_context,
                execution_approval=approval,
                allow_reviewed_writes=True,
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )

        self.assertTrue(result["execution_state"]["context_ready"])
        self.assertTrue(result["execution_state"]["execution_approved"])
        self.assertTrue(result["approval_scope"]["explicit_case_scope_present"])
        self.assertTrue(result["approval_scope"]["explicit_execution_mode_scope_present"])
        self.assertTrue(result["approval_scope"]["requested_case_in_scope"])
        self.assertTrue(result["approval_scope"]["requested_execution_mode_in_scope"])
        self.assertEqual(result["approval_scope"]["allowed_case_count"], 1)
        self.assertFalse(result["execution_state"]["executed"])
        self.assertEqual(result["result_class"], "not_run")
        self.assertIn("execution_not_requested", result["blocked_reasons"])
        self.assertFalse(result["confirmed_security_finding"])

    def test_execute_uses_sanitized_status_family_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attack = root / "live_attack_plan.json"
            write_context = root / "write_context.json"
            approval = root / "approval.json"
            _write_json(attack, _attack_plan())
            _write_json(write_context, _write_context())
            _write_json(approval, _approval("post_api_Users", ["live_reviewed_write_staging"]))

            with patch("adapters.live_replay.approved_context_replay.execute_live_case") as execute_case:
                execute_case.return_value = {
                    "case_id": "post_api_Users",
                    "method": "POST",
                    "success": False,
                    "status_code": 400,
                    "error": "http_error",
                    "response_headers": {"content-type": "application/json"},
                    "body_preview": "must-not-copy",
                }
                result = approved_context_replay(
                    attack,
                    case_id="post_api_Users",
                    write_context=write_context,
                    execution_approval=approval,
                    allow_reviewed_writes=True,
                    execute=True,
                    output_dir=root / "out",
                    fail_on_marker_hit=True,
                )
            output_json = (root / "out" / "approved_context_replay_result.json").read_text(encoding="utf-8")

        self.assertTrue(result["execution_state"]["executed"])
        self.assertEqual(result["result_class"], "safe_rejection")
        self.assertEqual(result["http_status_family"], "4xx")
        self.assertEqual(result["replay_failure_category"], "http_error")
        self.assertFalse(result["confirmed_security_finding"])
        self.assertEqual(result["case_evidence"]["body_field_count"], 1)
        self.assertNotIn("safe-placeholder", output_json)
        self.assertNotIn("must-not-copy", output_json)
        self.assertNotIn("response_headers", output_json)
        self.assertNotIn("body_preview", output_json)

    def test_builds_false_by_default_execution_approval_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attack = root / "live_attack_plan.json"
            write_context = root / "write_context.json"
            _write_json(attack, _attack_plan())
            _write_json(write_context, _write_context())
            approved_context_replay(
                attack,
                case_id="post_api_Users",
                write_context=write_context,
                allow_reviewed_writes=True,
                output_dir=root / "replay",
                fail_on_marker_hit=True,
            )

            request = build_execution_approval_request(
                root / "replay" / "approved_context_replay_plan.json",
                root / "replay" / "approved_context_replay_result.json",
                output_dir=root / "replay",
                fail_on_marker_hit=True,
            )
            template = json.loads((root / "replay" / "execution_approval.local.template.json").read_text(encoding="utf-8"))
            markdown = (root / "replay" / "execution_approval_request.md").read_text(encoding="utf-8")

        self.assertEqual(request["schema_version"], "adopt_redthread.approved_context_replay_execution_request.v1")
        self.assertEqual(request["request_status"], "ready_to_request_execution_approval")
        self.assertTrue(request["current_execution_state"]["context_ready"])
        self.assertFalse(request["current_execution_state"]["execution_approved"])
        self.assertFalse(request["current_execution_state"]["executed"])
        self.assertFalse(template["approved"])
        self.assertFalse(template["approved_non_production_scope"])
        self.assertFalse(template["operator_execution_approval_present"])
        self.assertEqual(template["allowed_case_ids"], ["post_api_Users"])
        self.assertIn("This request is not execution approval", markdown)
        self.assertTrue(request["output_marker_audit"]["passed"])

    def test_execution_approval_request_blocks_until_context_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attack = root / "live_attack_plan.json"
            _write_json(attack, _attack_plan())
            approved_context_replay(
                attack,
                case_id="post_api_Users",
                output_dir=root / "replay",
                fail_on_marker_hit=True,
            )

            request = build_execution_approval_request(
                root / "replay" / "approved_context_replay_plan.json",
                root / "replay" / "approved_context_replay_result.json",
                output_dir=root / "replay",
                fail_on_marker_hit=True,
            )

        self.assertEqual(request["request_status"], "blocked_until_runtime_context_ready")
        self.assertIn("approved_runtime_context_ready", request["blocked_until"])
        self.assertIn("sanitized_execution_approval_supplied", request["blocked_until"])

    def test_execution_approval_requires_explicit_case_and_mode_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attack = root / "live_attack_plan.json"
            approval = root / "approval.json"
            _write_json(attack, _attack_plan())
            missing_scope = _approval("post_api_Users", ["live_reviewed_write_staging"])
            missing_scope["allowed_case_ids"] = []
            missing_scope["allowed_execution_modes"] = []
            _write_json(approval, missing_scope)

            result = approved_context_replay(
                attack,
                case_id="post_api_Users",
                execution_approval=approval,
                fail_on_marker_hit=True,
            )

        self.assertFalse(result["execution_state"]["execution_approved"])
        self.assertIn("execution_approval_case_scope_missing", result["blocked_reasons"])
        self.assertIn("execution_approval_mode_scope_missing", result["blocked_reasons"])
        self.assertFalse(result["approval_scope"]["explicit_case_scope_present"])
        self.assertFalse(result["approval_scope"]["explicit_execution_mode_scope_present"])
        self.assertEqual(result["approval_scope"]["allowed_case_count"], 0)
        self.assertFalse(result["execution_state"]["executed"])
        self.assertFalse(result["release_gate_override"])

    def test_execution_approval_rejects_wildcard_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attack = root / "live_attack_plan.json"
            approval = root / "approval.json"
            _write_json(attack, _attack_plan())
            wildcard = _approval("post_api_Users", ["live_reviewed_write_staging"])
            wildcard["allowed_case_ids"] = ["*"]
            wildcard["allowed_execution_modes"] = ["*"]
            _write_json(approval, wildcard)

            result = approved_context_replay(
                attack,
                case_id="post_api_Users",
                execution_approval=approval,
                fail_on_marker_hit=True,
            )

        self.assertFalse(result["execution_state"]["execution_approved"])
        self.assertIn("wildcard_case_scope_not_allowed", result["blocked_reasons"])
        self.assertIn("wildcard_execution_mode_not_allowed", result["blocked_reasons"])
        self.assertTrue(result["approval_scope"]["wildcard_case_scope_requested"])
        self.assertTrue(result["approval_scope"]["wildcard_execution_mode_requested"])
        self.assertFalse(result["approval_scope"]["explicit_case_scope_present"])
        self.assertFalse(result["execution_state"]["executed"])

    def test_execution_approval_with_raw_field_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attack = root / "live_attack_plan.json"
            approval = root / "approval.json"
            _write_json(attack, _attack_plan())
            bad_approval = _approval("get_api_Profile", ["live_safe_read_with_approved_auth"])
            bad_approval["authorization"] = "should-not-appear"
            _write_json(approval, bad_approval)

            with self.assertRaises(RuntimeError):
                approved_context_replay(
                    attack,
                    case_id="get_api_Profile",
                    execution_approval=approval,
                    fail_on_marker_hit=True,
                )


def _attack_plan() -> dict[str, object]:
    return {
        "plan_id": "live-plan-test",
        "cases": [
            {
                "case_id": "get_api_Profile",
                "method": "GET",
                "path": "/api/Profile",
                "workflow_group": "api",
                "execution_mode": "live_safe_read_with_approved_auth",
                "approval_mode": "human_review",
                "side_effect_risk": "low",
                "allowed": False,
                "request_blueprint": {
                    "url": "https://example.test/api/Profile",
                    "host": "example.test",
                    "header_names": ["authorization"],
                    "query_params": [],
                    "body_fields": [],
                },
            },
            {
                "case_id": "post_api_Users",
                "method": "POST",
                "path": "/api/Users/",
                "workflow_group": "api",
                "execution_mode": "live_reviewed_write_staging",
                "approval_mode": "human_review",
                "side_effect_risk": "reviewed",
                "allowed": False,
                "request_blueprint": {
                    "url": "https://example.test/api/Users/",
                    "host": "example.test",
                    "header_names": [],
                    "query_params": [],
                    "body_fields": ["email"],
                },
            },
        ],
    }


def _write_context() -> dict[str, object]:
    return {
        "approved": True,
        "target_env": "staging",
        "target_base_url": "https://example.test",
        "target_hosts": ["example.test"],
        "case_approvals": {
            "post_api_Users": {
                "method": "POST",
                "path": "/api/Users/",
                "json_body": {"email": "safe-placeholder@example.test"},
                "headers": {},
            }
        },
    }


def _approval(case_id: str, modes: list[str]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_APPROVAL_VERSION,
        "approved": True,
        "approved_non_production_scope": True,
        "operator_execution_approval_present": True,
        "allowed_case_ids": [case_id],
        "allowed_execution_modes": modes,
        "approval_label": "approved_non_production_window_label",
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

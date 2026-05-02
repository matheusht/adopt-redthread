from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_boundary_probe_context import build_boundary_probe_context


class BoundaryProbeContextTests(unittest.TestCase):
    def test_writes_blocked_template_without_executing_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = _write_plan(root)
            design = _write_design(root)
            output = root / "context"

            payload = build_boundary_probe_context(
                probe_plan=plan,
                execution_design=design,
                output_dir=output,
                fail_on_marker_hit=True,
            )
            markdown = (output / "tenant_user_boundary_probe_context.template.md").read_text(encoding="utf-8")
            json_exists = (output / "tenant_user_boundary_probe_context.template.json").exists()

        self.assertEqual(payload["schema_version"], "adopt_redthread.boundary_probe_context.v1")
        self.assertEqual(payload["context_status"], "blocked_missing_context")
        self.assertFalse(payload["boundary_probe_execution_authorized"])
        self.assertFalse(payload["boundary_probe_executed"])
        self.assertFalse(payload["confirmed_security_finding"])
        self.assertEqual(payload["gate_decision"], "review")
        self.assertFalse(payload["verdict_semantics_changed"])
        self.assertEqual(payload["validation"]["blocker_count"], 1)
        self.assertIn("approved_non_production_target", payload["validation"]["missing_conditions"])
        self.assertIn("chatid", json.dumps(payload))
        self.assertTrue(json_exists)
        self.assertIn("# Tenant/User Boundary Probe Context Intake", markdown)
        self.assertIn("Context status: `blocked_missing_context`", markdown)
        self.assertNotIn("authorization:", markdown.casefold())
        self.assertNotIn("value_preview", markdown.casefold())

    def test_ready_for_boundary_probe_with_sanitized_approved_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / "context.json"
            _write_json(context, _valid_context())

            payload = build_boundary_probe_context(
                context=context,
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )

        self.assertEqual(payload["context_status"], "ready_for_boundary_probe")
        self.assertTrue(payload["boundary_probe_execution_authorized"])
        self.assertFalse(payload["boundary_probe_executed"])
        self.assertTrue(payload["validation"]["valid"])
        self.assertEqual(payload["validation"]["blocker_count"], 0)
        self.assertEqual(payload["normalized_context"]["target_environment"]["environment_label"], "staging_label")
        self.assertNotIn("actor_id", json.dumps(payload).casefold())
        self.assertNotIn("tenant_id", json.dumps(payload).casefold())
        self.assertTrue(payload["output_marker_audit"]["passed"])

    def test_production_or_expired_context_is_blocked_not_confirmed_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context_payload = _valid_context()
            context_payload["target_environment"]["production"] = True
            context_payload["operator_approval"]["expires_at"] = "2000-01-01T00:00:00Z"
            context = root / "context.json"
            _write_json(context, context_payload)

            payload = build_boundary_probe_context(
                context=context,
                output_dir=root / "out",
                fail_on_marker_hit=True,
            )

        codes = {item["code"] for item in payload["validation"]["blockers"]}
        self.assertEqual(payload["context_status"], "blocked_invalid_context")
        self.assertFalse(payload["boundary_probe_execution_authorized"])
        self.assertFalse(payload["confirmed_security_finding"])
        self.assertEqual(payload["gate_decision"], "review")
        self.assertIn("production_target", codes)
        self.assertIn("expired_context", codes)

    def test_context_with_raw_field_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context_payload = _valid_context()
            context_payload["actor_id"] = "should-not-appear"
            context = root / "context.json"
            _write_json(context, context_payload)

            with self.assertRaises(RuntimeError):
                build_boundary_probe_context(context=context, output_dir=root / "out", fail_on_marker_hit=True)

    def test_marker_hit_can_be_reported_as_privacy_blocked_when_not_failing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context_payload = _valid_context()
            context_payload["operator_approval"]["scope_note"] = "acct-123"
            context = root / "context.json"
            _write_json(context, context_payload)

            payload = build_boundary_probe_context(context=context, output_dir=root / "out", fail_on_marker_hit=False)

        self.assertEqual(payload["context_status"], "privacy_blocked")
        self.assertFalse(payload["boundary_probe_execution_authorized"])
        self.assertGreater(payload["input_marker_audit"]["marker_hit_count"], 0)


def _write_plan(root: Path) -> Path:
    path = root / "tenant_user_boundary_probe_plan.json"
    _write_json(
        path,
        {
            "schema_version": "adopt_redthread.boundary_probe_plan.v1",
            "candidate_summary": {
                "selectors": [
                    {
                        "name": "chatid",
                        "class": "resource",
                        "location": "body_field",
                        "operation_id": "op_004_post_api_chat",
                        "path_template": "/api/chat",
                    }
                ]
            },
        },
    )
    return path


def _write_design(root: Path) -> Path:
    path = root / "tenant_user_boundary_execution_design.json"
    _write_json(
        path,
        {
            "schema_version": "adopt_redthread.boundary_execution_design.v1",
            "approved_context_contract": {
                "schema_version": "adopt_redthread.boundary_probe_context.v1",
                "execution_mode": {
                    "allowed_values": ["safe_read_replay", "reviewed_non_production_workflow"]
                },
            },
        },
    )
    return path


def _valid_context() -> dict[str, object]:
    return {
        "schema_version": "adopt_redthread.boundary_probe_context.v1",
        "target_environment": {
            "environment_label": "staging_label",
            "base_url_label": "approved_base_label",
            "target_classification": "non_production",
            "production": False,
            "approved_for_boundary_probe": True,
        },
        "execution_mode": "safe_read_replay",
        "actor_scopes": {
            "scope_class": "cross_user_same_tenant",
            "actor_separation_confirmed": True,
            "own_scope": {
                "actor_label": "own_scope_actor_label",
                "tenant_scope_label": "tenant_scope_a_label",
            },
            "cross_scope": {
                "actor_label": "cross_scope_actor_label",
                "tenant_scope_label": "tenant_scope_a_label",
            },
        },
        "selector_bindings": [
            {
                "selector_name": "chatid",
                "selector_class": "resource",
                "selector_location": "body_field",
                "operation_id": "op_004_post_api_chat",
                "path_template": "/api/chat",
                "own_scope_value_ref": "context_ref.own_scope.chatid",
                "cross_scope_value_ref": "context_ref.cross_scope.chatid",
            }
        ],
        "operator_approval": {
            "approved_by_label": "operator_label",
            "approved_at": "2026-01-01T00:00:00Z",
            "expires_at": "2999-01-01T00:00:00Z",
            "scope_note": "approved non production boundary probe",
        },
        "safe_execution_constraints": {
            "approved_non_production_only": True,
            "no_raw_values_in_generated_artifacts": True,
            "no_production_writes": True,
            "future_executor_must_not_persist_resolved_values": True,
        },
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

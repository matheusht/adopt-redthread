from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_boundary_probe_context import SCHEMA_VERSION as CONTEXT_SCHEMA_VERSION
from scripts.build_boundary_probe_context import build_boundary_probe_context
from scripts.build_boundary_probe_context_request import build_boundary_probe_context_request


class BoundaryProbeContextRequestTests(unittest.TestCase):
    def test_builds_request_from_blocked_context_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = build_boundary_probe_context(output_dir=root / "context", fail_on_marker_hit=True)

            payload = build_boundary_probe_context_request(
                context_intake=root / "context" / "tenant_user_boundary_probe_context.template.json",
                output_dir=root / "request",
                fail_on_marker_hit=True,
            )

            self.assertEqual(context["context_status"], "blocked_missing_context")
            self.assertEqual(payload["schema_version"], "adopt_redthread.boundary_probe_context_request.v1")
            self.assertEqual(payload["request_status"], "ready_to_request_context")
            self.assertEqual(payload["source_context_status"], "blocked_missing_context")
            self.assertFalse(payload["boundary_probe_execution_authorized"])
            self.assertFalse(payload["boundary_probe_executed"])
            self.assertFalse(payload["confirmed_security_finding"])
            self.assertIn("approved_non_production_target", payload["missing_conditions"])
            self.assertIn("make evidence-boundary-probe-context BOUNDARY_CONTEXT=path/to/sanitized_context.json", payload["operator_commands"])
            rendered = (root / "request" / "tenant_user_boundary_probe_context_request.md").read_text(encoding="utf-8")
            self.assertIn("Request status: `ready_to_request_context`", rendered)
            self.assertNotIn("actor_id", rendered)
            self.assertNotIn("tenant_id", rendered)

    def test_ready_context_is_not_execution_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context_path = root / "ready_context.json"
            context_path.write_text(json.dumps({
                "schema_version": CONTEXT_SCHEMA_VERSION,
                "context_status": "ready_for_boundary_probe",
                "boundary_probe_execution_authorized": True,
                "boundary_probe_executed": False,
                "confirmed_security_finding": False,
                "validation": {"valid": True, "blocker_count": 0, "blockers": [], "missing_conditions": []},
                "context_template": {"schema_version": CONTEXT_SCHEMA_VERSION, "execution_mode": "safe_read_replay"},
            }), encoding="utf-8")

            payload = build_boundary_probe_context_request(
                context_intake=context_path,
                output_dir=root / "request",
                fail_on_marker_hit=True,
            )

            self.assertEqual(payload["request_status"], "context_ready")
            self.assertFalse(payload["boundary_probe_execution_authorized"])
            self.assertFalse(payload["boundary_probe_executed"])
            self.assertIn("boundary_probe_executed remains false until a separate approved executor exists", payload["acceptance_criteria"])

    def test_missing_context_intake_is_missing_required_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = build_boundary_probe_context_request(
                context_intake=root / "missing.json",
                output_dir=root / "request",
                fail_on_marker_hit=True,
            )

            self.assertEqual(payload["request_status"], "missing_required_evidence")
            self.assertIn("make evidence-boundary-probe-context", payload["operator_commands"])
            self.assertFalse(payload["boundary_probe_executed"])

    def test_context_template_values_are_not_copied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context_path = root / "context.json"
            context_path.write_text(json.dumps({
                "schema_version": CONTEXT_SCHEMA_VERSION,
                "context_status": "blocked_invalid_context",
                "validation": {"valid": False, "blocker_count": 1, "blockers": [], "missing_conditions": []},
                "context_template": {
                    "target_environment": {"base_url_label": "https://non-production.example.invalid/private-path"},
                    "selector_bindings": [{"own_scope_value_ref": "private-reference-label"}],
                },
            }), encoding="utf-8")

            payload = build_boundary_probe_context_request(
                context_intake=context_path,
                output_dir=root / "request",
                fail_on_marker_hit=True,
            )
            rendered_json = json.dumps(payload)
            self.assertNotIn("https://non-production.example.invalid/private-path", rendered_json)
            self.assertNotIn("private-reference-label", rendered_json)
            self.assertEqual(payload["sanitized_context_template"]["selector_bindings"], ["selector_binding_metadata_shape"])

    def test_raw_field_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context_path = root / "unsafe_context.json"
            context_path.write_text(json.dumps({"schema_version": CONTEXT_SCHEMA_VERSION, "actor_id": "do-not-copy"}), encoding="utf-8")

            with self.assertRaises(RuntimeError):
                build_boundary_probe_context_request(
                    context_intake=context_path,
                    output_dir=root / "request",
                    fail_on_marker_hit=True,
                )
            payload = build_boundary_probe_context_request(
                context_intake=context_path,
                output_dir=root / "request2",
                fail_on_marker_hit=False,
            )
            self.assertEqual(payload["request_status"], "privacy_blocked")
            self.assertEqual(payload["input_marker_audit"]["raw_field_keys"], ["redacted_raw_field_key"])


if __name__ == "__main__":
    unittest.main()

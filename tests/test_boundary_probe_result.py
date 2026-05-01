from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_boundary_probe_result import build_boundary_probe_result


class BoundaryProbeResultTests(unittest.TestCase):
    def test_builds_blocked_missing_context_result_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "tenant_user_boundary_probe_plan.json"
            design = root / "tenant_user_boundary_execution_design.json"
            output = root / "result"
            _write_json(
                plan,
                {
                    "schema_version": "adopt_redthread.boundary_probe_plan.v1",
                    "boundary_probe_status": "needs_boundary_probe",
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
            _write_json(
                design,
                {
                    "schema_version": "adopt_redthread.boundary_execution_design.v1",
                    "approved_context_contract": {
                        "schema_version": "adopt_redthread.boundary_probe_context.v1",
                        "storage_policy": "local_ignored_file_only_never_checked_in",
                        "required_top_level_fields": [
                            "schema_version",
                            "target_environment",
                            "execution_mode",
                            "actor_scopes",
                            "selector_bindings",
                            "operator_approval",
                        ],
                    },
                },
            )

            result = build_boundary_probe_result(
                probe_plan=plan,
                execution_design=design,
                output_dir=output,
                fail_on_marker_hit=True,
            )
            markdown = (output / "tenant_user_boundary_probe_result.md").read_text(encoding="utf-8")
            result_json_exists = (output / "tenant_user_boundary_probe_result.json").exists()

        self.assertEqual(result["schema_version"], "adopt_redthread.boundary_probe_result.v1")
        self.assertEqual(result["result_status"], "blocked_missing_context")
        self.assertFalse(result["boundary_probe_executed"])
        self.assertEqual(result["gate_decision"], "review")
        self.assertFalse(result["confirmed_security_finding"])
        self.assertEqual(result["selector_evidence"]["selector_name"], "chatid")
        self.assertEqual(result["own_scope_result_class"], "not_run")
        self.assertEqual(result["cross_scope_result_class"], "not_run")
        self.assertEqual(result["replay_failure_category"], "missing_approved_boundary_probe_context")
        self.assertTrue(result["configured_sensitive_marker_check"]["passed"])
        self.assertEqual(result["configured_sensitive_marker_check"]["marker_hit_count"], 0)
        self.assertEqual(result["configured_sensitive_marker_check"]["raw_field_hit_count"], 0)
        self.assertTrue(result_json_exists)
        self.assertIn("# Tenant/User Boundary Probe Result", markdown)
        self.assertIn("Result status: `blocked_missing_context`", markdown)
        self.assertIn("This artifact is an executor: `False`", markdown)
        self.assertIn("Missing boundary context is review evidence, not a confirmed vulnerability", markdown)
        self.assertNotIn("authorization:", markdown.casefold())
        self.assertNotIn("value_preview", markdown.casefold())

    def test_observed_result_with_raw_field_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observed = root / "observed.json"
            _write_json(
                observed,
                {
                    "result_status": "passed_boundary_probe",
                    "boundary_probe_executed": True,
                    "selector_evidence": {
                        "selector_name": "chatid",
                        "selector_class": "resource",
                        "selector_location": "body_field",
                        "operation_id": "op_004_post_api_chat",
                        "path_template": "/api/chat",
                    },
                    "own_scope_result_class": "allowed",
                    "cross_scope_result_class": "denied",
                    "http_status_family": "4xx",
                    "replay_failure_category": "none",
                    "gate_decision": "review",
                    "actor_id": "should-not-appear",
                },
            )

            with self.assertRaises(RuntimeError):
                build_boundary_probe_result(observed_result=observed, output_dir=root / "result", fail_on_marker_hit=True)

    def test_failed_boundary_probe_must_be_confirmed_security_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observed = root / "observed.json"
            _write_json(
                observed,
                {
                    "result_status": "failed_boundary_probe",
                    "boundary_probe_executed": True,
                    "selector_evidence": {
                        "selector_name": "chatid",
                        "selector_class": "resource",
                        "selector_location": "body_field",
                        "operation_id": "op_004_post_api_chat",
                        "path_template": "/api/chat",
                    },
                    "own_scope_result_class": "allowed",
                    "cross_scope_result_class": "allowed",
                    "http_status_family": "2xx",
                    "replay_failure_category": "none",
                    "gate_decision": "block",
                    "confirmed_security_finding": False,
                },
            )

            with self.assertRaises(ValueError):
                build_boundary_probe_result(observed_result=observed, output_dir=root / "result")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

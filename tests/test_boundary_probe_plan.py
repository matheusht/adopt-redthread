from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_boundary_probe_plan import build_boundary_probe_plan


class BoundaryProbePlanTests(unittest.TestCase):
    def test_builds_sanitized_plan_from_runtime_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            output_dir = root / "out"
            run_dir.mkdir()
            (run_dir / "workflow_summary.json").write_text(
                json.dumps({
                    "fixture_count": 1,
                    "redthread_replay_passed": True,
                    "redthread_dryrun_executed": True,
                    "app_context_summary": {
                        "auth_mode": "cookie",
                        "requires_approved_auth_context": True,
                        "requires_approved_write_context": True,
                        "candidate_boundary_selector_count": 1,
                        "candidate_resource_field_count": 1,
                        "boundary_reason_categories": ["resource_field_selector"],
                    },
                }),
                encoding="utf-8",
            )
            (run_dir / "redthread_runtime_inputs.json").write_text(
                json.dumps({
                    "app_context_summary": {
                        "auth_mode": "cookie",
                        "requires_approved_auth_context": True,
                        "requires_approved_write_context": True,
                        "candidate_boundary_selector_count": 1,
                        "candidate_resource_field_count": 1,
                        "boundary_reason_categories": ["resource_field_selector"],
                    },
                    "app_context": {
                        "tenant_user_boundary": {
                            "candidate_boundary_selectors": [{
                                "name": "chatid",
                                "location": "body_field",
                                "class": "resource",
                                "operation_id": "op_004_post_api_chat",
                                "path_template": "/api/chat",
                                "reason_category": "resource_field_selector",
                            }]
                        }
                    },
                }),
                encoding="utf-8",
            )

            plan = build_boundary_probe_plan(run_dir, output_dir=output_dir)
            markdown = (output_dir / "tenant_user_boundary_probe_plan.md").read_text(encoding="utf-8")

        self.assertEqual(plan["schema_version"], "adopt_redthread.boundary_probe_plan.v1")
        self.assertEqual(plan["boundary_probe_status"], "needs_boundary_probe")
        self.assertEqual(plan["candidate_summary"]["candidate_boundary_selector_count"], 1)
        self.assertEqual(plan["candidate_summary"]["selector_class_counts"], {"resource": 1})
        self.assertTrue(plan["safety_policy"]["plan_only_not_execution"])
        self.assertTrue(plan["decision_policy"]["no_verdict_change_from_plan_alone"])
        self.assertEqual(plan["configured_sensitive_marker_check"]["marker_hit_count"], 0)
        self.assertIn("# Tenant/User Boundary Probe Plan", markdown)
        self.assertIn("chatid", markdown)
        self.assertIn("Own-resource control succeeds", markdown)
        self.assertIn("Plan alone changes verdict: `False`", markdown)
        self.assertNotIn("authorization:", markdown.casefold())
        self.assertNotIn("value_preview", markdown.casefold())

    def test_marker_hit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "workflow_summary.json").write_text(json.dumps({"fixture_count": 1}), encoding="utf-8")
            (run_dir / "redthread_runtime_inputs.json").write_text(
                json.dumps({
                    "app_context": {
                        "tenant_user_boundary": {
                            "candidate_boundary_selectors": [{
                                "name": "authorization:",
                                "location": "body_field",
                                "class": "resource",
                            }]
                        }
                    },
                    "app_context_summary": {"candidate_boundary_selector_count": 1},
                }),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                build_boundary_probe_plan(run_dir, output_dir=root / "out")


if __name__ == "__main__":
    unittest.main()

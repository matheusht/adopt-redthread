from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_boundary_execution_design import build_boundary_execution_design


class BoundaryExecutionDesignTests(unittest.TestCase):
    def test_writes_design_and_result_contract_from_probe_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "tenant_user_boundary_probe_plan.json"
            output = root / "out"
            doc = root / "doc.md"
            plan.write_text(
                json.dumps({
                    "candidate_summary": {
                        "candidate_boundary_selector_count": 1,
                        "selector_class_counts": {"resource": 1},
                        "selector_location_counts": {"body_field": 1},
                        "reason_categories": ["resource_field_selector"],
                        "operation_ids": ["op_004_post_api_chat"],
                        "path_templates": ["/api/chat"],
                        "selectors": [{
                            "name": "chatid",
                            "class": "resource",
                            "location": "body_field",
                            "operation_id": "op_004_post_api_chat",
                            "path_template": "/api/chat",
                        }],
                    }
                }),
                encoding="utf-8",
            )

            payload = build_boundary_execution_design(
                probe_plan=plan,
                output_dir=output,
                doc_path=doc,
                fail_on_marker_hit=True,
            )
            markdown = doc.read_text(encoding="utf-8")

        self.assertEqual(payload["schema_version"], "adopt_redthread.boundary_execution_design.v1")
        self.assertEqual(payload["design_status"], "executor_not_implemented")
        self.assertEqual(payload["approved_context_contract"]["schema_version"], "adopt_redthread.boundary_probe_context.v1")
        self.assertEqual(payload["result_contract"]["schema_version"], "adopt_redthread.boundary_probe_result.v1")
        self.assertIn("passed_boundary_probe", payload["result_contract"]["allowed_statuses"])
        self.assertIn("failed_boundary_probe", payload["result_contract"]["allowed_statuses"])
        self.assertEqual(payload["configured_sensitive_marker_check"]["marker_hit_count"], 0)
        self.assertIn("# Tenant/User Boundary Execution Design", markdown)
        self.assertIn("This is not an executor", markdown)
        self.assertIn("own-scope control", markdown)
        self.assertIn("Auth/replay/context failures are not labeled as confirmed security findings", markdown)
        self.assertIn("adopt_redthread.boundary_probe_result.v1", markdown)
        self.assertNotIn("authorization:", markdown.casefold())
        self.assertNotIn("value_preview", markdown.casefold())

    def test_marker_hit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            plan.write_text(
                json.dumps({
                    "candidate_summary": {
                        "selectors": [{"name": "authorization:", "class": "resource"}],
                    }
                }),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                build_boundary_execution_design(
                    probe_plan=plan,
                    output_dir=root / "out",
                    doc_path=root / "doc.md",
                    fail_on_marker_hit=True,
                )


if __name__ == "__main__":
    unittest.main()

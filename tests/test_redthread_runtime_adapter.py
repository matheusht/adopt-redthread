from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from adapters.redthread_runtime.runtime_adapter import build_redthread_runtime_inputs


class RedThreadRuntimeAdapterTests(unittest.TestCase):
    def test_runtime_export_builds_replay_bundle_and_campaign_cases(self) -> None:
        bundle = json.loads(Path("fixtures/replay_packs/sample_har_fixture_bundle.json").read_text())
        payload = build_redthread_runtime_inputs(
            bundle,
            {
                "workflow_count": 1,
                "approved_binding_alias_count": 1,
                "approved_binding_alias_summary": {
                    "loaded_aliases": [{"source_key": "profile.id", "target_path": "profileKey", "tier": "reviewed_pattern"}],
                    "used_aliases": [{"workflow_id": "profile", "case_id": "step_b", "target_path": "profileKey"}],
                    "used_alias_count": 1,
                },
            },
        )

        self.assertEqual(payload["fixture_count"], 4)
        self.assertEqual(len(payload["redthread_replay_bundle"]["traces"]), 4)
        self.assertEqual(len(payload["campaign_cases"]), 4)

        first_trace = payload["redthread_replay_bundle"]["traces"][0]
        self.assertIn(first_trace["expected_authorization"], {"allow", "deny"})
        self.assertIn("action_envelope", first_trace["scenario_result"])
        self.assertIn("execution_policy", first_trace["scenario_result"])
        self.assertIn("objective", payload["campaign_cases"][0])
        self.assertIn("live_attack_candidates", payload)
        self.assertEqual(payload["bridge_workflow_context"]["approved_binding_alias_count"], 1)
        self.assertEqual(payload["bridge_workflow_context"]["approved_binding_alias_used_count"], 1)
        self.assertEqual(payload["bridge_workflow_context"]["planned_response_binding_count"], 0)
        self.assertEqual(payload["bridge_workflow_context"], payload["redthread_replay_bundle"]["bridge_workflow_context"])
        self.assertIn("app_context", payload)
        self.assertEqual(payload["app_context"], payload["bridge_workflow_context"]["app_context"])
        self.assertEqual(payload["app_context_summary"]["operation_count"], 4)

    def test_runtime_export_includes_minimum_sanitized_app_context(self) -> None:
        from adapters.zapi.loader import build_fixture_bundle

        payload = build_redthread_runtime_inputs(build_fixture_bundle("fixtures/zapi_samples/sample_filtered_har.json"))
        app_context = payload["app_context"]

        self.assertEqual(app_context["schema_version"], "app_context.v1")
        self.assertIn("workflow_order", app_context)
        self.assertIn("tool_action_schema", app_context)
        self.assertIn("auth_model", app_context)
        self.assertIn("data_sensitivity", app_context)
        self.assertIn("tenant_user_boundary", app_context)
        self.assertEqual(payload["app_context_summary"]["operation_count"], 4)
        self.assertEqual(app_context["auth_model"]["mode"], "api_key")
        self.assertTrue(app_context["auth_model"]["requires_approved_context"])
        self.assertIn("user_data", app_context["data_sensitivity"]["tags"])
        self.assertIn("financial_like", app_context["data_sensitivity"]["tags"])
        self.assertIn("user_id", app_context["tenant_user_boundary"]["candidate_user_fields"])
        self.assertIn("base_resp.status_code", app_context["tool_action_schema"][0]["response_fields"])

        serialized_context = json.dumps(app_context, sort_keys=True)
        raw_values_that_must_not_leak = _raw_har_values(Path("fixtures/zapi_samples/sample_filtered_har.json"))
        self.assertGreater(len(raw_values_that_must_not_leak), 0)
        for raw_value in raw_values_that_must_not_leak:
            self.assertNotIn(raw_value, serialized_context)

    def test_exported_bundle_can_be_evaluated_with_real_redthread_code(self) -> None:
        runtime_output = Path("fixtures/replay_packs/test_runtime_inputs.json")
        verdict_output = Path("fixtures/replay_packs/test_runtime_verdict.json")
        dryrun_output = Path("fixtures/replay_packs/test_runtime_dryrun.json")
        redthread_src = Path("../redthread/src").resolve()
        redthread_python = Path("../redthread/.venv/bin/python")

        subprocess.run(
            [
                sys.executable,
                "scripts/export_redthread_runtime_inputs.py",
                "fixtures/replay_packs/sample_har_fixture_bundle.json",
                str(runtime_output),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(redthread_python),
                "scripts/evaluate_redthread_replay.py",
                str(runtime_output),
                str(verdict_output),
                "--redthread-src",
                str(redthread_src),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(redthread_python),
                "scripts/run_redthread_dryrun.py",
                str(runtime_output),
                str(dryrun_output),
                "--redthread-src",
                str(redthread_src),
            ],
            check=True,
        )

        verdict = json.loads(verdict_output.read_text())
        dryrun = json.loads(dryrun_output.read_text())

        self.assertTrue(verdict["passed"])
        self.assertIn("campaign_id", dryrun)
        self.assertEqual(dryrun["rubric_name"], "prompt_injection")

        runtime_output.unlink(missing_ok=True)
        verdict_output.unlink(missing_ok=True)
        dryrun_output.unlink(missing_ok=True)


def _raw_har_values(path: Path) -> set[str]:
    raw = json.loads(path.read_text())
    values: set[str] = set()
    for entry in raw.get("log", {}).get("entries", []):
        request = entry.get("request", {})
        response = entry.get("response", {})
        for header in request.get("headers", []):
            _collect_scalar_values(header.get("value"), values)
        for query_param in request.get("queryString", []):
            _collect_scalar_values(query_param.get("value"), values)
        _collect_json_text_values(request.get("postData", {}).get("text"), values)
        _collect_json_text_values(response.get("content", {}).get("text"), values)
    return {value for value in values if len(value) > 5}


def _collect_json_text_values(raw_text: object, values: set[str]) -> None:
    if not isinstance(raw_text, str) or not raw_text:
        return
    values.add(raw_text)
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return
    _collect_scalar_values(payload, values)


def _collect_scalar_values(value: object, values: set[str]) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _collect_scalar_values(nested, values)
    elif isinstance(value, list):
        for nested in value:
            _collect_scalar_values(nested, values)
    elif value is not None:
        values.add(str(value))


if __name__ == "__main__":
    unittest.main()

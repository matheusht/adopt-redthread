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
        payload = build_redthread_runtime_inputs(bundle)

        self.assertEqual(payload["fixture_count"], 4)
        self.assertEqual(len(payload["redthread_replay_bundle"]["traces"]), 4)
        self.assertEqual(len(payload["campaign_cases"]), 4)

        first_trace = payload["redthread_replay_bundle"]["traces"][0]
        self.assertIn(first_trace["expected_authorization"], {"allow", "deny"})
        self.assertIn("action_envelope", first_trace["scenario_result"])
        self.assertIn("objective", payload["campaign_cases"][0])

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


if __name__ == "__main__":
    unittest.main()

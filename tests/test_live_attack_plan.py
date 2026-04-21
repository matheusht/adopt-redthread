from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from adapters.bridge.live_attack import build_live_attack_plan
from adapters.zapi.loader import build_fixture_bundle


class LiveAttackPlanTests(unittest.TestCase):
    def test_plan_marks_sample_har_cases_as_review_or_blocked(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_filtered_har.json")
        plan = build_live_attack_plan(bundle)

        self.assertEqual(plan["fixture_count"], 4)
        self.assertEqual(plan["allowed_case_count"], 0)
        self.assertTrue(plan["blocked_case_count"] >= 0)
        first_case = plan["cases"][0]
        self.assertIn(first_case["execution_mode"], {"manual_review", "sandbox_only"})
        self.assertEqual(first_case["request_blueprint"]["host"], "www.talkie-ai.com")

    def test_cli_writes_plan_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "live_attack_plan.json"
            subprocess.run(
                [
                    "python3",
                    "scripts/generate_live_attack_plan.py",
                    "fixtures/zapi_samples/sample_filtered_har.json",
                    str(output),
                    "--ingestion",
                    "zapi",
                ],
                check=True,
            )
            payload = json.loads(output.read_text())
            self.assertEqual(payload["fixture_count"], 4)
            self.assertIn("cases", payload)


if __name__ == "__main__":
    unittest.main()

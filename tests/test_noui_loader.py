from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from adapters.noui.loader import build_noui_fixture_bundle
from adapters.redthread_runtime.runtime_adapter import build_redthread_runtime_inputs


class NouiLoaderTests(unittest.TestCase):
    def test_noui_manifest_and_tools_map_into_fixture_bundle(self) -> None:
        bundle = build_noui_fixture_bundle("fixtures/noui_samples/expedia_stay_search")

        self.assertEqual(bundle["source"], "noui_mcp")
        self.assertEqual(bundle["ingestion_mode"], "mcp_server")
        self.assertEqual(bundle["fixture_count"], 1)

        fixture = bundle["fixtures"][0]
        self.assertEqual(fixture["name"], "search_hotels")
        self.assertEqual(fixture["replay_class"], "safe_read_with_review")
        self.assertIn("authorization_bypass", fixture["candidate_attack_types"])
        self.assertIn("overbroad_data_access", fixture["candidate_attack_types"])
        self.assertIn("cdp_browser_fetch", fixture["auth_hints"])

    def test_noui_bundle_flows_into_redthread_runtime_export_and_eval(self) -> None:
        fixture_output = Path("fixtures/replay_packs/test_noui_fixture_bundle.json")
        runtime_output = Path("fixtures/replay_packs/test_noui_runtime_inputs.json")
        verdict_output = Path("fixtures/replay_packs/test_noui_runtime_verdict.json")

        subprocess.run(
            [
                "python3",
                "scripts/ingest_noui.py",
                "fixtures/noui_samples/expedia_stay_search",
                str(fixture_output),
            ],
            check=True,
        )

        bundle = json.loads(fixture_output.read_text())
        runtime_payload = build_redthread_runtime_inputs(bundle)
        runtime_output.write_text(json.dumps(runtime_payload, indent=2) + "\n")

        subprocess.run(
            [
                "../redthread/.venv/bin/python",
                "scripts/evaluate_redthread_replay.py",
                str(runtime_output),
                str(verdict_output),
                "--redthread-src",
                str(Path("../redthread/src").resolve()),
            ],
            check=True,
        )

        verdict = json.loads(verdict_output.read_text())
        self.assertTrue(verdict["passed"])

        fixture_output.unlink(missing_ok=True)
        runtime_output.unlink(missing_ok=True)
        verdict_output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

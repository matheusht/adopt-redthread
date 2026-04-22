from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from adapters.bridge.workflow import run_bridge_workflow


class BridgeWorkflowTests(unittest.TestCase):
    def test_full_bridge_workflow_runs_from_sample_har(self) -> None:
        output_dir = Path("runs/test_sample_har_bridge")
        if output_dir.exists():
            for path in sorted(output_dir.glob("**/*"), reverse=True):
                if path.is_file():
                    path.unlink()
            for path in sorted(output_dir.glob("**/*"), reverse=True):
                if path.is_dir():
                    path.rmdir()

        summary = run_bridge_workflow(
            "fixtures/zapi_samples/sample_filtered_har.json",
            ingestion="zapi",
            output_dir=output_dir,
            redthread_python="../redthread/.venv/bin/python",
            redthread_src="../redthread/src",
        )

        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["fixture_count"], 4)
        self.assertTrue(summary["redthread_replay_passed"])
        self.assertTrue(summary["redthread_dryrun_executed"])

        workflow_summary = json.loads((output_dir / "workflow_summary.json").read_text())
        live_attack_plan = json.loads((output_dir / "live_attack_plan.json").read_text())
        gate_verdict = json.loads((output_dir / "gate_verdict.json").read_text())
        self.assertEqual(workflow_summary["gate_decision"], "review")
        self.assertIn("live_attack_allowed_count", workflow_summary)
        self.assertIn("live_workflow_requirement_summary", workflow_summary)
        self.assertEqual(workflow_summary["live_workflow_requirement_summary"], {})
        self.assertEqual(live_attack_plan["fixture_count"], 4)
        self.assertTrue(gate_verdict["evidence_summary"]["redthread_replay_verdict"]["passed"])

    def test_cli_bridge_pipeline_emits_summary_json(self) -> None:
        output_dir = Path("runs/test_cli_bridge")
        subprocess.run(
            [
                "python3",
                "scripts/run_bridge_pipeline.py",
                "fixtures/zapi_samples/sample_filtered_har.json",
                str(output_dir),
                "--ingestion",
                "zapi",
                "--redthread-python",
                "../redthread/.venv/bin/python",
                "--redthread-src",
                "../redthread/src",
            ],
            check=True,
        )
        summary = json.loads((output_dir / "workflow_summary.json").read_text())
        self.assertEqual(summary["status"], "completed")
        self.assertTrue(summary["redthread_replay_passed"])
        self.assertIn("live_attack_allowed_count", summary)


if __name__ == "__main__":
    unittest.main()

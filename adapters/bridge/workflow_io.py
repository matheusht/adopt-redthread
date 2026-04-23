from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def run_redthread_replay(*, repo_root: Path, runtime_input: Path, output_path: Path, redthread_python: Path, redthread_src: Path) -> dict[str, Any]:
    subprocess.run(
        [
            str(redthread_python),
            str(repo_root / "scripts" / "evaluate_redthread_replay.py"),
            str(runtime_input),
            str(output_path),
            "--redthread-src",
            str(redthread_src),
        ],
        check=True,
    )
    return json.loads(output_path.read_text())


def run_redthread_dryrun(*, repo_root: Path, runtime_input: Path, output_path: Path, redthread_python: Path, redthread_src: Path) -> dict[str, Any]:
    subprocess.run(
        [
            str(redthread_python),
            str(repo_root / "scripts" / "run_redthread_dryrun.py"),
            str(runtime_input),
            str(output_path),
            "--redthread-src",
            str(redthread_src),
        ],
        check=True,
    )
    return json.loads(output_path.read_text())


def artifact_paths(output_root: Path) -> dict[str, Path]:
    return {
        "fixture_bundle": output_root / "fixture_bundle.json",
        "replay_plan": output_root / "replay_plan.json",
        "gate_verdict": output_root / "gate_verdict.json",
        "runtime_inputs": output_root / "redthread_runtime_inputs.json",
        "live_attack_plan": output_root / "live_attack_plan.json",
        "live_workflow_plan": output_root / "live_workflow_plan.json",
        "live_safe_replay": output_root / "live_safe_replay.json",
        "live_workflow_replay": output_root / "live_workflow_replay.json",
        "binding_history": output_root / "binding_history.jsonl",
        "binding_pattern_candidates": output_root / "binding_pattern_candidates.json",
        "replay_verdict": output_root / "redthread_replay_verdict.json",
        "dryrun_case0": output_root / "redthread_dryrun_case0.json",
        "summary": output_root / "workflow_summary.json",
        "workflow_review_manifest": output_root / "workflow_review_manifest.json",
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")

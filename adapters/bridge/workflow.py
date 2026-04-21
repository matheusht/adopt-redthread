from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adapters.adopt_actions.loader import build_action_fixture_bundle
from adapters.bridge.live_attack import build_live_attack_plan
from adapters.noui.loader import build_noui_fixture_bundle
from adapters.redthread_runtime.runtime_adapter import build_redthread_runtime_inputs
from adapters.zapi.loader import build_fixture_bundle as build_zapi_fixture_bundle
from scripts.generate_replay_pack import build_replay_pack
from scripts.prepublish_gate import build_gate_verdict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REDTHREAD_PYTHON = REPO_ROOT.parent / "redthread" / ".venv" / "bin" / "python"
DEFAULT_REDTHREAD_SRC = REPO_ROOT.parent / "redthread" / "src"


def run_bridge_workflow(
    input_path: str | Path,
    *,
    ingestion: str,
    output_dir: str | Path,
    allow_sandbox_only: bool = False,
    run_dryrun: bool = True,
    redthread_python: str | Path = DEFAULT_REDTHREAD_PYTHON,
    redthread_src: str | Path = DEFAULT_REDTHREAD_SRC,
) -> dict[str, Any]:
    input_file = Path(input_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    bundle = _build_bundle(input_file, ingestion)
    replay_pack = build_replay_pack(bundle)
    gate_verdict = build_gate_verdict(replay_pack, allow_sandbox_only=allow_sandbox_only)
    runtime_inputs = build_redthread_runtime_inputs(bundle)
    live_attack_plan = build_live_attack_plan(bundle)

    paths = _artifact_paths(output_root)
    _write_json(paths["fixture_bundle"], bundle)
    _write_json(paths["replay_plan"], replay_pack)
    _write_json(paths["gate_verdict"], gate_verdict)
    _write_json(paths["runtime_inputs"], runtime_inputs)
    _write_json(paths["live_attack_plan"], live_attack_plan)

    replay_verdict = _run_replay(runtime_input=paths["runtime_inputs"], output_path=paths["replay_verdict"], redthread_python=Path(redthread_python), redthread_src=Path(redthread_src))
    dryrun_summary: dict[str, Any] | None = None
    if run_dryrun:
        dryrun_summary = _run_dryrun(runtime_input=paths["runtime_inputs"], output_path=paths["dryrun_case0"], redthread_python=Path(redthread_python), redthread_src=Path(redthread_src))

    summary = {
        "status": "completed",
        "ingestion": ingestion,
        "input_file": str(input_file),
        "output_dir": str(output_root),
        "fixture_count": bundle.get("fixture_count", 0),
        "gate_decision": gate_verdict["decision"],
        "live_attack_allowed_count": live_attack_plan["allowed_case_count"],
        "live_attack_blocked_count": live_attack_plan["blocked_case_count"],
        "redthread_replay_passed": replay_verdict["passed"],
        "redthread_dryrun_executed": dryrun_summary is not None,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": {name: str(path) for name, path in paths.items()},
    }
    if dryrun_summary is not None:
        summary["dryrun_case_id"] = dryrun_summary["case_id"]
        summary["dryrun_rubric_name"] = dryrun_summary["rubric_name"]
    _write_json(paths["summary"], summary)
    return summary


def _build_bundle(input_file: Path, ingestion: str) -> dict[str, Any]:
    builders = {
        "zapi": build_zapi_fixture_bundle,
        "noui": build_noui_fixture_bundle,
        "adopt_actions": build_action_fixture_bundle,
    }
    if ingestion not in builders:
        raise ValueError(f"Unsupported ingestion mode: {ingestion}")
    return builders[ingestion](input_file)


def _run_replay(*, runtime_input: Path, output_path: Path, redthread_python: Path, redthread_src: Path) -> dict[str, Any]:
    subprocess.run(
        [
            str(redthread_python),
            str(REPO_ROOT / "scripts" / "evaluate_redthread_replay.py"),
            str(runtime_input),
            str(output_path),
            "--redthread-src",
            str(redthread_src),
        ],
        check=True,
    )
    return json.loads(output_path.read_text())


def _run_dryrun(*, runtime_input: Path, output_path: Path, redthread_python: Path, redthread_src: Path) -> dict[str, Any]:
    subprocess.run(
        [
            str(redthread_python),
            str(REPO_ROOT / "scripts" / "run_redthread_dryrun.py"),
            str(runtime_input),
            str(output_path),
            "--redthread-src",
            str(redthread_src),
        ],
        check=True,
    )
    return json.loads(output_path.read_text())


def _artifact_paths(output_root: Path) -> dict[str, Path]:
    return {
        "fixture_bundle": output_root / "fixture_bundle.json",
        "replay_plan": output_root / "replay_plan.json",
        "gate_verdict": output_root / "gate_verdict.json",
        "runtime_inputs": output_root / "redthread_runtime_inputs.json",
        "live_attack_plan": output_root / "live_attack_plan.json",
        "replay_verdict": output_root / "redthread_replay_verdict.json",
        "dryrun_case0": output_root / "redthread_dryrun_case0.json",
        "summary": output_root / "workflow_summary.json",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")

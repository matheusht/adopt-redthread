from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adapters.adopt_actions.loader import build_action_fixture_bundle
from adapters.bridge.live_attack import build_live_attack_plan
from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.bridge.workflow_io import artifact_paths, export_optional_json_artifact, run_redthread_dryrun, run_redthread_replay, write_json
from adapters.bridge.workflow_review_manifest import build_workflow_review_manifest, enrich_manifest_candidates
from adapters.live_replay.binding_patterns import build_binding_pattern_candidates
from adapters.live_replay.executor import execute_live_safe_replay
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
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
    run_live_safe_replay: bool = False,
    run_live_workflow_replay: bool = False,
    auth_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_auth: bool = False,
    write_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_writes: bool = False,
    stream_max_bytes: int = 512,
    binding_overrides: dict[str, Any] | str | Path | None = None,
    approved_binding_aliases: dict[str, Any] | str | Path | None = None,
    redthread_python: str | Path = DEFAULT_REDTHREAD_PYTHON,
    redthread_src: str | Path = DEFAULT_REDTHREAD_SRC,
) -> dict[str, Any]:
    input_file = Path(input_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    bundle = _build_bundle(input_file, ingestion)
    replay_pack = build_replay_pack(bundle)
    live_attack_plan = build_live_attack_plan(bundle)
    live_workflow_plan = build_live_workflow_plan(
        live_attack_plan,
        binding_overrides,
        approved_binding_aliases,
    )

    runtime_inputs = build_redthread_runtime_inputs(bundle, live_workflow_plan)
    paths = artifact_paths(output_root)
    write_json(paths["fixture_bundle"], bundle)
    write_json(paths["replay_plan"], replay_pack)
    write_json(paths["runtime_inputs"], runtime_inputs)
    write_json(paths["live_attack_plan"], live_attack_plan)
    write_json(paths["live_workflow_plan"], live_workflow_plan)
    approved_alias_artifact_ready = export_optional_json_artifact(paths["approved_binding_aliases"], approved_binding_aliases)

    cases = {str(case.get("case_id", "")): case for case in live_attack_plan.get("cases", [])}
    workflow_review_manifest = build_workflow_review_manifest(live_workflow_plan, None, cases)
    write_json(paths["workflow_review_manifest"], workflow_review_manifest)

    live_safe_replay_summary: dict[str, Any] | None = None
    if run_live_safe_replay:
        live_safe_replay_summary = execute_live_safe_replay(
            live_attack_plan,
            auth_context=auth_context,
            allow_reviewed_auth=allow_reviewed_auth,
            write_context=write_context,
            allow_reviewed_writes=allow_reviewed_writes,
            output_path=paths["live_safe_replay"],
            stream_max_bytes=stream_max_bytes,
        )

    live_workflow_summary: dict[str, Any] | None = None
    if run_live_workflow_replay:
        live_workflow_summary = execute_live_workflow_replay(
            live_workflow_plan,
            live_attack_plan,
            auth_context=auth_context,
            allow_reviewed_auth=allow_reviewed_auth,
            write_context=write_context,
            allow_reviewed_writes=allow_reviewed_writes,
            output_path=paths["live_workflow_replay"],
            binding_history_path=paths["binding_history"],
            stream_max_bytes=stream_max_bytes,
        )

    binding_pattern_candidates: dict[str, Any] | None = None
    if live_workflow_summary is not None:
        runtime_inputs = build_redthread_runtime_inputs(bundle, live_workflow_plan, live_workflow_summary)
        write_json(paths["runtime_inputs"], runtime_inputs)
        workflow_review_manifest = build_workflow_review_manifest(live_workflow_plan, live_workflow_summary, cases)
        workflow_review_manifest = enrich_manifest_candidates(workflow_review_manifest, live_workflow_summary, cases)
        write_json(paths["workflow_review_manifest"], workflow_review_manifest)
        binding_pattern_candidates = build_binding_pattern_candidates(
            paths["binding_history"],
            output_path=paths["binding_pattern_candidates"],
        )

    replay_verdict = run_redthread_replay(
        repo_root=REPO_ROOT,
        runtime_input=paths["runtime_inputs"],
        output_path=paths["replay_verdict"],
        redthread_python=Path(redthread_python),
        redthread_src=Path(redthread_src),
    )
    gate_verdict = build_gate_verdict(
        replay_pack,
        allow_sandbox_only=allow_sandbox_only,
        live_safe_replay=live_safe_replay_summary,
        live_workflow_replay=live_workflow_summary,
        redthread_replay_verdict=replay_verdict,
        workflow_plan=live_workflow_plan,
    )
    write_json(paths["gate_verdict"], gate_verdict)
    dryrun_summary: dict[str, Any] | None = None
    if run_dryrun:
        dryrun_summary = run_redthread_dryrun(
            repo_root=REPO_ROOT,
            runtime_input=paths["runtime_inputs"],
            output_path=paths["dryrun_case0"],
            redthread_python=Path(redthread_python),
            redthread_src=Path(redthread_src),
        )

    visible_artifacts = {
        name: str(path)
        for name, path in paths.items()
        if (name != "live_safe_replay" or live_safe_replay_summary is not None)
        and (name != "live_workflow_replay" or live_workflow_summary is not None)
        and (name != "binding_history" or (live_workflow_summary is not None and live_workflow_summary.get("binding_history_rows_written", 0) > 0))
        and (name != "binding_pattern_candidates" or binding_pattern_candidates is not None)
        and (name != "approved_binding_aliases" or approved_alias_artifact_ready)
    }
    summary = {
        "status": "completed",
        "ingestion": ingestion,
        "input_file": str(input_file),
        "output_dir": str(output_root),
        "fixture_count": bundle.get("fixture_count", 0),
        "gate_decision": gate_verdict["decision"],
        "live_attack_allowed_count": live_attack_plan["allowed_case_count"],
        "live_attack_blocked_count": live_attack_plan["blocked_case_count"],
        "live_workflow_count": live_workflow_plan["workflow_count"],
        "approved_binding_alias_count": live_workflow_plan.get("approved_binding_alias_count", 0),
        "approved_binding_alias_summary": live_workflow_plan.get("approved_binding_alias_summary", {}),
        "live_safe_replay_executed": live_safe_replay_summary is not None,
        "live_safe_replay_count": 0 if live_safe_replay_summary is None else live_safe_replay_summary["executed_case_count"],
        "live_safe_replay_used_auth_context": False if live_safe_replay_summary is None else live_safe_replay_summary.get("auth_context_used", False),
        "live_safe_replay_used_write_context": False if live_safe_replay_summary is None else live_safe_replay_summary.get("write_context_used", False),
        "live_workflow_replay_executed": live_workflow_summary is not None,
        "live_workflow_replay_count": 0 if live_workflow_summary is None else live_workflow_summary["executed_workflow_count"],
        "live_workflow_blocked_count": 0 if live_workflow_summary is None else live_workflow_summary.get("blocked_workflow_count", 0),
        "live_workflow_aborted_count": 0 if live_workflow_summary is None else live_workflow_summary.get("aborted_workflow_count", 0),
        "live_workflow_reason_counts": {} if live_workflow_summary is None else live_workflow_summary.get("reason_counts", {}),
        "live_workflow_requirement_summary": {} if live_workflow_summary is None else live_workflow_summary.get("workflow_requirement_summary", {}),
        "live_workflow_failure_class_summary": {} if live_workflow_summary is None else live_workflow_summary.get("workflow_failure_class_summary", {}),
        "live_workflow_binding_application_summary": {} if live_workflow_summary is None else live_workflow_summary.get("binding_application_summary", {}),
        "live_workflow_binding_review_artifacts": [] if live_workflow_summary is None else live_workflow_summary.get("workflow_binding_review_artifacts", []),
        "live_workflow_review_manifest_ready": bool(workflow_review_manifest.get("workflows")),
        "binding_history_rows_written": 0 if live_workflow_summary is None else live_workflow_summary.get("binding_history_rows_written", 0),
        "binding_pattern_candidate_count": 0 if binding_pattern_candidates is None else binding_pattern_candidates.get("candidate_count", 0),
        "binding_pattern_promotion_ready_count": 0 if binding_pattern_candidates is None else binding_pattern_candidates.get("promotion_ready_count", 0),
        "redthread_replay_passed": replay_verdict["passed"],
        "redthread_dryrun_executed": dryrun_summary is not None,
        "app_context_summary": runtime_inputs.get("app_context_summary", {}),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": visible_artifacts,
    }
    if dryrun_summary is not None:
        summary["dryrun_case_id"] = dryrun_summary["case_id"]
        summary["dryrun_rubric_name"] = dryrun_summary["rubric_name"]
    write_json(paths["summary"], summary)
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

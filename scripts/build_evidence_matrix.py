from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.bridge.evidence_summaries import build_attack_brief_summary, build_coverage_summary, build_decision_reason_summary
from scripts.generate_hero_binding_truth import build_hero_artifacts
from scripts.generate_reviewed_write_reference import run_reviewed_write_reference

DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "evidence_matrix"
DEFAULT_VICTORIA_EXPECTED = REPO_ROOT / "fixtures" / "reference_demos" / "victoria_expected_block.json"


AGENTS = {
    "approve": {
        "name": "ReleaseApprovalAgent",
        "responsibility": "Approve only when workflow evidence and RedThread replay pass with no blockers or review warnings.",
    },
    "review": {
        "name": "SecurityReviewAgent",
        "responsibility": "Hold human review when write paths or other review warnings are present without blockers.",
    },
    "block": {
        "name": "SafetyBlockAgent",
        "responsibility": "Block release when required context is missing, live workflow evidence fails, or RedThread replay fails.",
    },
}


def build_evidence_matrix(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    hero_run_dir: str | Path = REPO_ROOT / "runs" / "hero_binding_truth",
    reviewed_run_dir: str | Path = REPO_ROOT / "runs" / "reviewed_write_reference",
    victoria_run_dir: str | Path = REPO_ROOT / "runs" / "victoria",
    victoria_expected: str | Path = DEFAULT_VICTORIA_EXPECTED,
    regenerate: bool = True,
    redthread_python: str | Path = REPO_ROOT.parent / "redthread" / ".venv" / "bin" / "python",
    redthread_src: str | Path = REPO_ROOT.parent / "redthread" / "src",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    if regenerate:
        build_hero_artifacts(hero_run_dir)
        run_reviewed_write_reference(
            reviewed_run_dir,
            redthread_python=redthread_python,
            redthread_src=redthread_src,
            run_dryrun=True,
        )

    rows = [
        _row_from_run("hero_binding_truth", "approve", Path(hero_run_dir), "deterministic safe-read binding demo"),
        _row_from_run("reviewed_write_reference", "review", Path(reviewed_run_dir), "deterministic reviewed-write demo"),
        _victoria_row(Path(victoria_run_dir), Path(victoria_expected)),
    ]
    matrix = {
        "schema_version": "adopt_redthread.evidence_matrix.v1",
        "artifact_policy": "Matrix contains sanitized summaries only. Raw HAR/session/cookie/body/run artifacts stay ignored under runs/.",
        "rows": rows,
    }
    (output_root / "evidence_matrix.json").write_text(json.dumps(matrix, indent=2) + "\n")
    (output_root / "evidence_matrix.md").write_text(_markdown(matrix), encoding="utf-8")
    return matrix


def _victoria_row(run_dir: Path, expected_path: Path) -> dict[str, Any]:
    if (run_dir / "workflow_summary.json").exists():
        return _row_from_run("victoria_expected_block", "block", run_dir, "Victoria HAR block example")
    expected_doc = _load(expected_path)
    expected = expected_doc["expected"]
    agent = AGENTS["block"]
    summary = {
        "fixture_count": expected["fixture_count"],
        "live_workflow_count": expected["workflow_count"],
        "live_workflow_reason_counts": {expected["workflow_reason"]: 1},
        "live_workflow_requirement_summary": {"workflow_class_counts": {expected["workflow_class"]: 1}},
        "redthread_replay_passed": expected["redthread_replay_passed"],
        "gate_decision": expected["gate_decision"],
        "app_context_summary": expected.get("app_context_summary", {}),
    }
    gate = {"decision": expected["gate_decision"], "warnings": [], "blockers": [expected["gate_blocker"]]}
    live_workflow = {"reason_counts": {expected["workflow_reason"]: 1}, "blocked_workflow_count": 1, "successful_workflow_count": 0}
    return {
        "scenario_id": "victoria_expected_block",
        "scenario_label": "Victoria HAR block example",
        "outcome_slot": "block",
        "decision_agent": agent["name"],
        "agent_responsibility": agent["responsibility"],
        "artifact_source": _display_path(expected_path),
        "input_artifact": expected_doc["input_file_basename"],
        "fixture_count": expected["fixture_count"],
        "workflow_count": expected["workflow_count"],
        "workflow_classes": expected["workflow_class"],
        "binding_planned": expected["declared_response_binding_count"],
        "binding_applied": expected["applied_response_binding_count"],
        "binding_failed": expected["unapplied_response_binding_count"],
        **_app_context_cells(expected.get("app_context_summary", {})),
        **_engine_summary_cells(summary, gate, live_workflow, {}),
        "redthread_replay_passed": expected["redthread_replay_passed"],
        "gate_decision": expected["gate_decision"],
        "exact_reason": f"{expected['gate_blocker']} / {expected['workflow_reason']}",
        "redthread_control_detail": expected["redthread_control_detail"],
        "raw_artifact_policy": expected_doc["artifact_policy"],
    }


def _row_from_run(scenario_id: str, outcome_slot: str, run_dir: Path, label: str) -> dict[str, Any]:
    summary = _load(run_dir / "workflow_summary.json")
    gate = _load(run_dir / "gate_verdict.json")
    live_workflow = _load_optional(run_dir / "live_workflow_replay.json") or {}
    runtime_inputs = _load_optional(run_dir / "redthread_runtime_inputs.json") or {}
    redthread = _load_optional(run_dir / "redthread_replay_verdict.json") or {}

    requirement = summary.get("live_workflow_requirement_summary") or live_workflow.get("workflow_requirement_summary", {})
    binding = summary.get("live_workflow_binding_application_summary") or live_workflow.get("binding_application_summary", {})
    app_context_summary = summary.get("app_context_summary") or runtime_inputs.get("app_context_summary", {})
    agent = AGENTS[outcome_slot]
    return {
        "scenario_id": scenario_id,
        "scenario_label": label,
        "outcome_slot": outcome_slot,
        "decision_agent": agent["name"],
        "agent_responsibility": agent["responsibility"],
        "artifact_source": str(run_dir),
        "input_artifact": Path(str(summary.get("input_file", "unknown"))).name,
        "fixture_count": summary.get("fixture_count", _runtime_fixture_count(runtime_inputs)),
        "workflow_count": summary.get("live_workflow_count", live_workflow.get("workflow_count", 0)),
        "workflow_classes": _flat_counts(requirement.get("workflow_class_counts", {})),
        "binding_planned": binding.get("planned_response_binding_count", requirement.get("declared_response_binding_count", 0)),
        "binding_applied": binding.get("applied_response_binding_count", requirement.get("applied_response_binding_count", 0)),
        "binding_failed": binding.get("unapplied_response_binding_count", 0),
        **_app_context_cells(app_context_summary),
        **_engine_summary_cells(summary, gate, live_workflow, runtime_inputs),
        "redthread_replay_passed": bool(redthread.get("passed", summary.get("redthread_replay_passed", False))),
        "gate_decision": gate.get("decision", summary.get("gate_decision", "unknown")),
        "exact_reason": _exact_reason(gate, summary, live_workflow),
        "redthread_control_detail": _control_detail(runtime_inputs),
        "raw_artifact_policy": "local ignored run artifact; do not commit raw run files",
    }


def _app_context_cells(summary: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(summary, dict) or not summary:
        return {
            "app_context_summary": "n/a",
            "app_context_auth_summary": "n/a",
            "app_context_sensitivity": "n/a",
        }
    action_classes = _flat_counts(summary.get("action_class_counts", {}))
    schema = summary.get("schema_version", "n/a")
    operations = summary.get("operation_count", 0)
    tools = summary.get("tool_action_schema_count", 0)
    auth_mode = summary.get("auth_mode", "unknown")
    auth_scope = _join(summary.get("auth_scope_hints", []))
    approved_auth = summary.get("requires_approved_auth_context", summary.get("requires_approved_context", False))
    approved_write = summary.get("requires_approved_write_context", summary.get("requires_approved_context", False))
    boundary = (
        f"user_fields:{summary.get('candidate_user_field_count', 0)},"
        f"tenant_fields:{summary.get('candidate_tenant_field_count', 0)},"
        f"resource_fields:{summary.get('candidate_resource_field_count', 0)},"
        f"route_params:{summary.get('candidate_route_param_count', 0)},"
        f"selectors:{summary.get('candidate_boundary_selector_count', 0)},"
        f"reasons:{_join(summary.get('boundary_reason_categories', []))}"
    )
    return {
        "app_context_summary": f"{schema}; ops:{operations}; schemas:{tools}; actions:{action_classes}",
        "app_context_auth_summary": f"mode:{auth_mode}; scopes:{auth_scope}; approved_auth:{approved_auth}; approved_write:{approved_write}",
        "app_context_sensitivity": f"tags:{_join(summary.get('data_sensitivity_tags', []))}; boundary:{boundary}",
    }


def _engine_summary_cells(summary: dict[str, Any], gate: dict[str, Any], live_workflow: dict[str, Any], runtime_inputs: dict[str, Any]) -> dict[str, Any]:
    app_context_summary = summary.get("app_context_summary") or runtime_inputs.get("app_context_summary", {})
    decision_reason = summary.get("decision_reason_summary") or build_decision_reason_summary(gate, summary, live_workflow=live_workflow)
    coverage = summary.get("coverage_summary") or build_coverage_summary(summary, live_workflow=live_workflow, app_context_summary=app_context_summary)
    attack_brief = summary.get("attack_brief_summary") or runtime_inputs.get("attack_brief_summary") or build_attack_brief_summary(
        runtime_inputs.get("app_context", {}),
        app_context_summary,
        dryrun_rubric_name=summary.get("dryrun_rubric_name"),
        dryrun_rubric_rationale=summary.get("dryrun_rubric_rationale"),
    )
    return {
        "decision_reason_category": decision_reason.get("category", "unknown"),
        "confirmed_security_finding": bool(decision_reason.get("confirmed_security_finding", False)),
        "coverage_label": coverage.get("label", "unknown"),
        "coverage_gaps": _join(coverage.get("coverage_gaps", [])),
        "top_targeted_probe": attack_brief.get("top_targeted_probe", "n/a"),
        "dryrun_rubric_rationale": attack_brief.get("dryrun_rubric_rationale", "n/a"),
    }



def _exact_reason(gate: dict[str, Any], summary: dict[str, Any], live_workflow: dict[str, Any]) -> str:
    decision = str(gate.get("decision", summary.get("gate_decision", "unknown")))
    blockers = gate.get("blockers", [])
    warnings = gate.get("warnings", [])
    if decision == "approve":
        return "no blockers or warnings"
    if decision == "review":
        return _join(warnings)
    reason_counts = live_workflow.get("reason_counts") or summary.get("live_workflow_reason_counts", {})
    if reason_counts:
        return f"{_join(blockers)} / {_flat_counts(reason_counts)}"
    return _join(blockers)


def _control_detail(runtime_inputs: dict[str, Any]) -> str:
    traces = runtime_inputs.get("redthread_replay_bundle", {}).get("traces", [])
    if not traces:
        return "n/a"
    auth_matches = 0
    canary_contained = 0
    canary_total = 0
    decisions: set[str] = set()
    for trace in traces:
        actual = (trace.get("authorization_decision") or {}).get("decision")
        expected = trace.get("expected_authorization")
        if actual:
            decisions.add(str(actual))
        if expected is not None and actual == expected:
            auth_matches += 1
        if trace.get("expect_canary_contained") is not None:
            canary_total += 1
            if bool((trace.get("canary_report") or {}).get("contained")) == bool(trace.get("expect_canary_contained")):
                canary_contained += 1
    parts = []
    if auth_matches:
        parts.append(f"authorization matched expected for {auth_matches}/{len(traces)} traces ({','.join(sorted(decisions))})")
    if canary_total:
        parts.append(f"canary containment matched for {canary_contained}/{canary_total} traces")
    return "; ".join(parts) if parts else "RedThread replay traces present"


def _runtime_fixture_count(runtime_inputs: dict[str, Any]) -> int:
    value = runtime_inputs.get("fixture_count")
    return int(value) if isinstance(value, int) else 0


def _markdown(matrix: dict[str, Any]) -> str:
    rows = matrix["rows"]
    lines = [
        "# Evidence Matrix",
        "",
        matrix["artifact_policy"],
        "",
        "RedThread replay/dry-run is evidence; the final `approve` / `review` / `block` verdict is currently emitted by the local Adopt RedThread bridge gate.",
        "",
        "| Outcome | Responsible agent | Scenario | Input | Fixtures | Workflows | Bindings planned/applied/failed | App context | Auth context | Sensitivity | Decision reason | Coverage | Top targeted probe | Dry-run rationale | RedThread replay | Local gate decision | Exact reason | Control detail |",
        "|---|---|---|---|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {outcome_slot} | {decision_agent} | {scenario_label} | `{input_artifact}` | {fixture_count} | {workflow_count} | {binding_planned}/{binding_applied}/{binding_failed} | {app_context_summary} | {app_context_auth_summary} | {app_context_sensitivity} | {decision_reason_category}; confirmed:{confirmed_security_finding} | {coverage_label}; gaps:{coverage_gaps} | {top_targeted_probe} | {dryrun_rubric_rationale} | {redthread_replay_passed} | `{gate_decision}` | {exact_reason} | {redthread_control_detail} |".format(
                **{key: _md_escape(value) for key, value in row.items()}
            )
        )
    lines.extend([
        "",
        "## Agent responsibility rules",
        "",
        f"- **{AGENTS['approve']['name']}**: {AGENTS['approve']['responsibility']}",
        f"- **{AGENTS['review']['name']}**: {AGENTS['review']['responsibility']}",
        f"- **{AGENTS['block']['name']}**: {AGENTS['block']['responsibility']}",
        "",
    ])
    return "\n".join(lines)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _md_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _flat_counts(payload: dict[str, Any]) -> str:
    if not payload:
        return "none"
    return ",".join(f"{key}:{payload[key]}" for key in sorted(payload))


def _join(items: list[Any]) -> str:
    return "none" if not items else ",".join(str(item) for item in items)


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"required evidence artifact missing: {path}")
    return json.loads(path.read_text())


def _load_optional(path: Path) -> dict[str, Any] | None:
    return _load(path) if path.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build approve/review/block evidence matrix from local demo runs.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--hero-run-dir", default="runs/hero_binding_truth")
    parser.add_argument("--reviewed-run-dir", default="runs/reviewed_write_reference")
    parser.add_argument("--victoria-run-dir", default="runs/victoria")
    parser.add_argument("--victoria-expected", default=str(DEFAULT_VICTORIA_EXPECTED))
    parser.add_argument("--use-existing", action="store_true", help="Do not regenerate deterministic approve/review runs")
    parser.add_argument("--redthread-python", default=str(REPO_ROOT.parent / "redthread" / ".venv" / "bin" / "python"))
    parser.add_argument("--redthread-src", default=str(REPO_ROOT.parent / "redthread" / "src"))
    args = parser.parse_args()

    matrix = build_evidence_matrix(
        output_dir=args.output_dir,
        hero_run_dir=args.hero_run_dir,
        reviewed_run_dir=args.reviewed_run_dir,
        victoria_run_dir=args.victoria_run_dir,
        victoria_expected=args.victoria_expected,
        regenerate=not args.use_existing,
        redthread_python=args.redthread_python,
        redthread_src=args.redthread_src,
    )
    print(f"evidence matrix -> {Path(args.output_dir) / 'evidence_matrix.md'}")
    print(json.dumps({"row_count": len(matrix["rows"]), "decisions": [row["gate_decision"] for row in matrix["rows"]]}, indent=2))


if __name__ == "__main__":
    main()

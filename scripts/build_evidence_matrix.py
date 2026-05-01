from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.bridge.evidence_summaries import build_attack_brief_summary, build_auth_diagnostics_summary, build_coverage_summary, build_decision_reason_summary, build_rerun_trigger_summary
from scripts.generate_hero_binding_truth import build_hero_artifacts
from scripts.generate_reviewed_write_reference import run_reviewed_write_reference

DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "evidence_matrix"
DEFAULT_VICTORIA_EXPECTED = REPO_ROOT / "fixtures" / "reference_demos" / "victoria_expected_block.json"
BOUNDARY_RESULT_FILENAME = "tenant_user_boundary_probe_result.json"


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
        "reviewer_action": _reviewer_action(gate, summary, live_workflow, {}),
        "exact_reason": f"{expected['gate_blocker']} / {expected['workflow_reason']}",
        "redthread_control_detail": expected["redthread_control_detail"],
        "boundary_probe_result": _boundary_result_cell(None, expected.get("coverage_summary", {})),
        "raw_artifact_policy": expected_doc["artifact_policy"],
    }


def _row_from_run(scenario_id: str, outcome_slot: str, run_dir: Path, label: str) -> dict[str, Any]:
    summary = _load(run_dir / "workflow_summary.json")
    gate = _load(run_dir / "gate_verdict.json")
    live_workflow = _load_optional(run_dir / "live_workflow_replay.json") or {}
    runtime_inputs = _load_optional(run_dir / "redthread_runtime_inputs.json") or {}
    redthread = _load_optional(run_dir / "redthread_replay_verdict.json") or {}
    boundary_result = _load_boundary_result(run_dir, allow_shared=(scenario_id == "reviewed_write_reference"))

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
        **_engine_summary_cells(summary, gate, live_workflow, runtime_inputs, boundary_result=boundary_result),
        "redthread_replay_passed": bool(redthread.get("passed", summary.get("redthread_replay_passed", False))),
        "gate_decision": gate.get("decision", summary.get("gate_decision", "unknown")),
        "reviewer_action": _reviewer_action(gate, summary, live_workflow, runtime_inputs),
        "exact_reason": _exact_reason(gate, summary, live_workflow),
        "redthread_control_detail": _control_detail(runtime_inputs),
        "boundary_probe_result": _boundary_result_cell(boundary_result, summary.get("coverage_summary", {})),
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


def _engine_summary_cells(
    summary: dict[str, Any],
    gate: dict[str, Any],
    live_workflow: dict[str, Any],
    runtime_inputs: dict[str, Any],
    *,
    boundary_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    app_context_summary = summary.get("app_context_summary") or runtime_inputs.get("app_context_summary", {})
    decision_reason = summary.get("decision_reason_summary") or build_decision_reason_summary(gate, summary, live_workflow=live_workflow)
    coverage = summary.get("coverage_summary") or build_coverage_summary(summary, live_workflow=live_workflow, app_context_summary=app_context_summary)
    attack_brief = summary.get("attack_brief_summary") or runtime_inputs.get("attack_brief_summary") or build_attack_brief_summary(
        runtime_inputs.get("app_context", {}),
        app_context_summary,
        dryrun_rubric_name=summary.get("dryrun_rubric_name"),
        dryrun_rubric_rationale=summary.get("dryrun_rubric_rationale"),
    )
    auth_diagnostics = summary.get("auth_diagnostics_summary") or build_auth_diagnostics_summary(
        summary,
        live_workflow=live_workflow,
        app_context_summary=app_context_summary,
    )
    binding_audit = summary.get("live_workflow_binding_audit_summary") or live_workflow.get("binding_audit_summary", {})
    rerun_triggers = build_rerun_trigger_summary(coverage, auth_diagnostics, binding_audit, app_context_summary)
    return {
        "decision_reason_category": decision_reason.get("category", "unknown"),
        "confirmed_security_finding": bool(decision_reason.get("confirmed_security_finding", False)),
        "finding_type": _finding_type_cell(decision_reason, auth_diagnostics),
        "trusted_evidence": _trusted_evidence_cell(summary, live_workflow),
        "coverage_label": coverage.get("label", "unknown"),
        "coverage_gaps": _join(coverage.get("coverage_gaps", [])),
        "auth_replay_failure_category": auth_diagnostics.get("replay_failure_category", "unknown"),
        "auth_context_gap": bool(auth_diagnostics.get("auth_context_gap", False)),
        "write_context_gap": bool(auth_diagnostics.get("write_context_gap", False)),
        "binding_audit": _binding_audit_cell(binding_audit),
        "next_evidence_needed": _next_evidence_cell(coverage, auth_diagnostics, binding_audit, attack_brief, boundary_result=boundary_result),
        "rerun_triggers": _rerun_trigger_cell(rerun_triggers),
        "top_targeted_probe": attack_brief.get("top_targeted_probe", "n/a"),
        "dryrun_rubric_rationale": attack_brief.get("dryrun_rubric_rationale", "n/a"),
    }



def _rerun_trigger_cell(rerun_trigger_summary: dict[str, Any]) -> str:
    triggers = [str(item) for item in rerun_trigger_summary.get("triggers", []) if str(item).strip()]
    return "; ".join(triggers) if triggers else "evidence_envelope_changes"



def _next_evidence_cell(
    coverage: dict[str, Any],
    auth_diagnostics: dict[str, Any],
    binding_audit: dict[str, Any],
    attack_brief: dict[str, Any],
    *,
    boundary_result: dict[str, Any] | None = None,
) -> str:
    gaps = {str(item) for item in coverage.get("coverage_gaps", [])}
    replay_failure = str(auth_diagnostics.get("replay_failure_category", "unknown"))
    parts: list[str] = []
    if auth_diagnostics.get("write_context_gap") or replay_failure == "missing_write_context":
        parts.append("approved staging write context + workflow rerun")
    if auth_diagnostics.get("auth_context_gap") or replay_failure in {"missing_auth_context", "auth_header_family_mismatch", "server_rejected_auth"}:
        parts.append("approved auth context refresh + replay rerun")
    if "workflow_blocked" in gaps:
        parts.append("resolve workflow blocker + rerun")
    unapplied = int(binding_audit.get("unapplied_binding_count", 0) or 0)
    pending = int((binding_audit.get("status_counts", {}) or {}).get("pending", 0) or 0)
    if "bindings_not_fully_applied" in gaps or unapplied or pending:
        parts.append("binding review + continuity rerun")
    if "tenant_user_boundary_unproven" in gaps:
        boundary_status = str((boundary_result or {}).get("result_status", "absent"))
        if boundary_status == "blocked_missing_context":
            parts.append("approved boundary context + sanitized boundary result")
        elif boundary_status == "auth_or_replay_failed":
            parts.append("resolve boundary auth/replay failure + rerun boundary probe")
        else:
            probe = attack_brief.get("top_targeted_probe", "ownership-boundary probe")
            parts.append(f"ownership-boundary probe: {probe}")
    if "no_live_or_workflow_replay" in gaps:
        parts.append("bounded safe/workflow replay")
    return "; ".join(dict.fromkeys(parts)) if parts else "no additional evidence request emitted"



def _trusted_evidence_cell(summary: dict[str, Any], live_workflow: dict[str, Any]) -> str:
    parts: list[str] = []
    workflow_count = int(summary.get("live_workflow_count", live_workflow.get("workflow_count", 0)) or 0)
    workflow_executed = bool(summary.get("live_workflow_replay_executed", False) or live_workflow or workflow_count)
    if workflow_executed:
        successful = int(live_workflow.get("successful_workflow_count", summary.get("successful_workflow_count", 0)) or 0)
        blocked = int(live_workflow.get("blocked_workflow_count", summary.get("blocked_workflow_count", 0)) or 0)
        aborted = int(live_workflow.get("aborted_workflow_count", summary.get("aborted_workflow_count", 0)) or 0)
        if successful or blocked or aborted:
            parts.append(f"workflow status successful:{successful},blocked:{blocked},aborted:{aborted}")
        else:
            parts.append(f"workflow evidence present:{workflow_count}")
    requirement = summary.get("live_workflow_requirement_summary", {})
    binding = summary.get("live_workflow_binding_application_summary", {})
    planned = binding.get("planned_response_binding_count", requirement.get("declared_response_binding_count", 0))
    applied = binding.get("applied_response_binding_count", requirement.get("applied_response_binding_count", 0))
    if planned:
        parts.append(f"bindings applied:{applied}/{planned}")
    if "redthread_replay_passed" in summary:
        parts.append(f"RedThread replay passed:{bool(summary.get('redthread_replay_passed'))}")
    if summary.get("redthread_dryrun_executed", False):
        parts.append(f"RedThread dry-run rubric:{summary.get('dryrun_rubric_name', 'n/a')}")
    return "; ".join(parts) if parts else "fixture/summary evidence only"



def _finding_type_cell(decision_reason: dict[str, Any], auth_diagnostics: dict[str, Any]) -> str:
    category = str(decision_reason.get("category", "unknown"))
    if decision_reason.get("confirmed_security_finding", False):
        return f"confirmed security finding; category:{category}"
    replay_failure = str(auth_diagnostics.get("replay_failure_category", "unknown"))
    if category == "auth_or_context_blocked" or replay_failure not in {"none", "unknown", "None", ""}:
        return f"auth/replay/context failure:{replay_failure}; not confirmed vulnerability"
    if category in {"insufficient_coverage", "tenant_boundary_unproven", "binding_review_needed"}:
        return f"insufficient or unproven evidence:{category}; not confirmed vulnerability"
    return f"not confirmed security finding; category:{category}"



def _reviewer_action(gate: dict[str, Any], summary: dict[str, Any], live_workflow: dict[str, Any], runtime_inputs: dict[str, Any]) -> str:
    app_context_summary = summary.get("app_context_summary") or runtime_inputs.get("app_context_summary", {})
    decision_reason = summary.get("decision_reason_summary") or build_decision_reason_summary(gate, summary, live_workflow=live_workflow)
    coverage = summary.get("coverage_summary") or build_coverage_summary(summary, live_workflow=live_workflow, app_context_summary=app_context_summary)
    decision = str(gate.get("decision", summary.get("gate_decision", "unknown")))
    category = str(decision_reason.get("category", "unknown"))
    label = str(coverage.get("label", "unknown"))
    gaps = _join(coverage.get("coverage_gaps", []))
    if decision == "approve":
        return f"ship candidate: local gate approved; coverage:{label}; gaps:{gaps}"
    if decision == "review":
        return f"change/review before ship: {category}; coverage:{label}; gaps:{gaps}"
    if decision == "block" and category == "auth_or_context_blocked":
        primary = decision_reason.get("primary_reason", "required_context_missing")
        return f"block until approved context/replay gap is resolved: {primary}; coverage:{label}; gaps:{gaps}"
    if decision == "block":
        return f"block release: {category}; coverage:{label}; gaps:{gaps}"
    return f"manual triage required: {category}; coverage:{label}; gaps:{gaps}"



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


def _load_boundary_result(run_dir: Path, *, allow_shared: bool = False) -> dict[str, Any] | None:
    paths = [run_dir / BOUNDARY_RESULT_FILENAME]
    if allow_shared:
        paths.append(run_dir.parent / "boundary_probe_result" / BOUNDARY_RESULT_FILENAME)
    for path in paths:
        if path.exists():
            loaded = _load_optional(path)
            if isinstance(loaded, dict) and loaded.get("schema_version") == "adopt_redthread.boundary_probe_result.v1":
                return loaded
    return None


def _boundary_result_cell(boundary_result: dict[str, Any] | None, coverage: dict[str, Any]) -> str:
    gaps = {str(item) for item in coverage.get("coverage_gaps", [])} if isinstance(coverage, dict) else set()
    if not boundary_result:
        if "tenant_user_boundary_unproven" in gaps:
            return "absent; tenant_user_boundary_unproven"
        return "absent"
    selector = boundary_result.get("selector_evidence", {}) if isinstance(boundary_result.get("selector_evidence"), dict) else {}
    selector_label = "/".join(str(selector.get(key, "unknown")) for key in ("selector_class", "selector_location", "operation_id"))
    return (
        f"status:{boundary_result.get('result_status', 'unknown')}; "
        f"executed:{boundary_result.get('boundary_probe_executed', False)}; "
        f"selector:{selector_label}; "
        f"own_cross:{boundary_result.get('own_scope_result_class', 'unknown')}/{boundary_result.get('cross_scope_result_class', 'unknown')}; "
        f"finding:{boundary_result.get('confirmed_security_finding', False)}"
    )


def _binding_audit_cell(binding_audit: dict[str, Any]) -> str:
    if not binding_audit:
        return "n/a"
    return (
        f"status:{_flat_counts(binding_audit.get('status_counts', {}))}; "
        f"origin:{_flat_counts(binding_audit.get('origin_counts', {}))}; "
        f"changed:{binding_audit.get('changed_later_request_count', 0)}"
    )


def _markdown(matrix: dict[str, Any]) -> str:
    rows = matrix["rows"]
    lines = [
        "# Evidence Matrix",
        "",
        matrix["artifact_policy"],
        "",
        "RedThread replay/dry-run is evidence; the final `approve` / `review` / `block` verdict is currently emitted by the local Adopt RedThread bridge gate.",
        "",
        "## How to read this matrix",
        "",
        "- Each row is a tested evidence envelope, not a whole-app safety proof.",
        "- `approve` means ship candidate for the tested envelope only.",
        "- `review` means change/review before ship, commonly for write-capable or human-sensitive paths.",
        "- `block` means do not ship from this run until required context, replay, or evidence blockers are resolved.",
        "- Finding type separates confirmed findings from auth/replay/context failures and insufficient evidence.",
        "",
        "| Outcome | Responsible agent | Scenario | Input | Fixtures | Workflows | Bindings planned/applied/failed | App context | Auth context | Sensitivity | Decision reason | Finding type | Trusted evidence | Coverage | Auth/replay diagnostics | Binding audit | Boundary probe result | Next evidence needed | Rerun triggers | Top targeted probe | Dry-run rationale | RedThread replay | Local gate decision | Reviewer action | Exact reason | Control detail |",
        "|---|---|---|---|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {outcome_slot} | {decision_agent} | {scenario_label} | `{input_artifact}` | {fixture_count} | {workflow_count} | {binding_planned}/{binding_applied}/{binding_failed} | {app_context_summary} | {app_context_auth_summary} | {app_context_sensitivity} | {decision_reason_category}; confirmed:{confirmed_security_finding} | {finding_type} | {trusted_evidence} | {coverage_label}; gaps:{coverage_gaps} | category:{auth_replay_failure_category}; auth_gap:{auth_context_gap}; write_gap:{write_context_gap} | {binding_audit} | {boundary_probe_result} | {next_evidence_needed} | {rerun_triggers} | {top_targeted_probe} | {dryrun_rubric_rationale} | {redthread_replay_passed} | `{gate_decision}` | {reviewer_action} | {exact_reason} | {redthread_control_detail} |".format(
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

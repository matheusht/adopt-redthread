from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_evidence_report(run_dir: str | Path, output_path: str | Path | None = None) -> str:
    root = Path(run_dir)
    summary = _load(root / "workflow_summary.json")
    gate = _load(root / "gate_verdict.json")
    workflow = _load_optional(root / "live_workflow_replay.json")
    redthread = _load_optional(root / "redthread_replay_verdict.json")

    requirement_summary = summary.get("live_workflow_requirement_summary", {})
    binding_summary = summary.get("live_workflow_binding_application_summary", {})
    workflow_status = _workflow_status(workflow)
    redthread_passed = redthread.get("passed") if redthread else summary.get("redthread_replay_passed")

    lines = [
        f"# Evidence Report: {root.name}",
        "",
        "## Decision",
        "",
        f"- Local gate decision: `{gate.get('decision', summary.get('gate_decision', 'unknown'))}`",
        f"- Gate warnings: `{_join(gate.get('warnings', []))}`",
        f"- Gate blockers: `{_join(gate.get('blockers', []))}`",
        "",
        "## Input",
        "",
        f"- Ingestion: `{summary.get('ingestion', 'unknown')}`",
        f"- Input artifact: `{Path(str(summary.get('input_file', 'unknown'))).name}`",
        f"- Fixture count: `{summary.get('fixture_count', 0)}`",
        "",
        "## Workflow evidence",
        "",
        f"- Live workflow replay executed: `{summary.get('live_workflow_replay_executed', False)}`",
        f"- Workflow count: `{summary.get('live_workflow_count', 0)}`",
        f"- Successful workflows: `{workflow_status['successful']}`",
        f"- Blocked workflows: `{workflow_status['blocked']}`",
        f"- Aborted workflows: `{workflow_status['aborted']}`",
        f"- Workflow classes: `{_flat_counts(requirement_summary.get('workflow_class_counts', {}))}`",
        f"- Failure classes: `{_flat_counts(summary.get('live_workflow_failure_class_summary', {}))}`",
        "",
        "## Binding evidence",
        "",
        f"- Declared response bindings: `{requirement_summary.get('declared_response_binding_count', binding_summary.get('planned_response_binding_count', 0))}`",
        f"- Applied response bindings: `{requirement_summary.get('applied_response_binding_count', binding_summary.get('applied_response_binding_count', 0))}`",
        f"- Unapplied response bindings: `{binding_summary.get('unapplied_response_binding_count', 0)}`",
        f"- Binding failures: `{_flat_counts(binding_summary.get('binding_application_failure_counts', {}))}`",
        "",
        "## RedThread evidence",
        "",
        f"- RedThread replay passed: `{bool(redthread_passed)}`",
        f"- RedThread dry-run executed: `{summary.get('redthread_dryrun_executed', False)}`",
        f"- Dry-run case: `{summary.get('dryrun_case_id', 'n/a')}`",
        f"- Dry-run rubric: `{summary.get('dryrun_rubric_name', 'n/a')}`",
        "",
        "## Why this decision is correct",
        "",
        _decision_narrative(gate, summary),
        "",
        "## Not proven by this run",
        "",
        "- production publish gating wired into a real release system",
        "- stable behavior of any external live app forever",
        "- RedThread independently owning live workflow execution for Adopt-managed sessions",
        "- broad authenticated/write-path coverage beyond this reviewed reference path",
        "",
    ]
    report = "\n".join(lines)
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
    return report


def _decision_narrative(gate: dict[str, Any], summary: dict[str, Any]) -> str:
    decision = str(gate.get("decision", summary.get("gate_decision", "unknown")))
    warnings = gate.get("warnings", [])
    blockers = gate.get("blockers", [])
    if decision == "approve":
        return "The workflow evidence and RedThread evidence passed with no blockers or review warnings."
    if decision == "review" and "manual_review_required_for_write_paths" in warnings:
        return "The workflow succeeded and RedThread replay passed, but write paths are present. The correct safe outcome is human review, not silent approval."
    if decision == "block":
        return "The gate found blocking evidence that must be fixed or explicitly re-run before this can be treated as publishable."
    return "The gate emitted this decision from the combined bridge replay evidence and RedThread evidence."


def _workflow_status(workflow: dict[str, Any] | None) -> dict[str, int]:
    if not workflow:
        return {"successful": 0, "blocked": 0, "aborted": 0}
    return {
        "successful": int(workflow.get("successful_workflow_count", 0)),
        "blocked": int(workflow.get("blocked_workflow_count", 0)),
        "aborted": int(workflow.get("aborted_workflow_count", 0)),
    }


def _flat_counts(payload: dict[str, Any]) -> str:
    if not payload:
        return "none"
    return ",".join(f"{key}:{payload[key]}" for key in sorted(payload))


def _join(items: list[Any]) -> str:
    return "none" if not items else ",".join(str(item) for item in items)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _load_optional(path: Path) -> dict[str, Any] | None:
    return _load(path) if path.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a markdown evidence report from a bridge run directory.")
    parser.add_argument("--run-dir", default="runs/reviewed_write_reference", help="Run directory containing workflow_summary.json")
    parser.add_argument("--output", default=None, help="Output markdown path; defaults to <run-dir>/evidence_report.md")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    output = Path(args.output) if args.output else run_dir / "evidence_report.md"
    report = build_evidence_report(run_dir, output)
    print(f"evidence report -> {output}")
    print(report)


if __name__ == "__main__":
    main()

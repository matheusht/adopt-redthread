#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_sanitized_intent_review import build_sanitized_intent_review

EVAL_SCHEMA_VERSION = "adopt_redthread.local_intent_review_eval.v0"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _case_specs(boundary_rubric: str | None, reviewer_observations: str | None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = [
        {
            "case_id": "baseline_parity_no_context",
            "description": "No optional boundary/reviewer context; useful local LLM behavior is cautious parity or explicitly bounded uncertainty.",
            "expect_useful_delta": False,
            "boundary_rubric": None,
            "reviewer_observations": None,
        }
    ]
    if boundary_rubric and reviewer_observations:
        cases.append({
            "case_id": "context_enriched_review",
            "description": "Sanitized boundary rubric and reviewer observations are present; useful local LLM behavior may add more specific advisory intent/questions without overclaiming.",
            "expect_useful_delta": True,
            "boundary_rubric": boundary_rubric,
            "reviewer_observations": reviewer_observations,
        })
    return cases


def _summarize_case(case: dict[str, Any], deterministic_dir: Path, local_dir: Path, elapsed: float) -> dict[str, Any]:
    deterministic_md = (deterministic_dir / "intent_review.md").read_text(encoding="utf-8")
    local_md = (local_dir / "intent_review.md").read_text(encoding="utf-8")
    local_status = _read_json(local_dir / "local_llm_status.json")
    privacy = _read_json(local_dir / "privacy_audit.json")
    schema = _read_json(local_dir / "schema_validation.json")
    export = _read_json(local_dir / "redthread_evidence_export.json")
    handoff = _read_json(local_dir / "redthread_execution_handoff.json")
    handoff_validation = _read_json(local_dir / "redthread_execution_handoff_validation.json")
    intent_evidence_validation = _read_json(local_dir / "redthread_intent_evidence_validation.json")
    importability = _read_json(local_dir / "redthread_importability_report.json")
    workflow_import = _read_json(local_dir / "redthread_candidate_workflow_import.json")
    product_proof = _read_json(local_dir / "redthread_product_proof.json")
    candidates = handoff.get("execution_candidates", [])
    empty_diff = deterministic_md == local_md
    deterministic_review = _read_json(deterministic_dir / "intent_review.json")
    local_review = _read_json(local_dir / "intent_review.json")
    observation_delta = deterministic_review.get("subjects", []) != local_review.get("subjects", [])
    local_observation_flag = any(
        bool(subject.get("local_model_observations", {}).get("useful_delta"))
        for subject in local_review.get("subjects", [])
    )
    forbidden_claim_count = int(privacy.get("forbidden_claim_language_hit_count", 0))
    execution_candidate_present = bool(candidates)
    candidate_has_observation_citations = bool(candidates) and all(bool(c.get("supporting_sanitized_observations")) for c in candidates)
    next_redthread_action_clear = bool(candidates) and all(bool(c.get("recommended_redthread_action")) for c in candidates)
    missing_context_clear = bool(candidates) and all("missing_context" in c for c in candidates)
    handoff_useful = (
        execution_candidate_present
        and candidate_has_observation_citations
        and next_redthread_action_clear
        and missing_context_clear
        and bool(handoff_validation.get("passed"))
        and bool(handoff.get("summary", {}).get("redthread_final_gate_required"))
        and not bool(handoff.get("summary", {}).get("live_execution_allowed"))
    )
    redthread_importable = bool(importability.get("importable"))
    candidate_workflow_created = bool(workflow_import.get("candidate_workflow_count", 0))
    product_proof_passed = bool(product_proof.get("passed"))
    judge_required = bool(importability.get("judge_required")) and all(
        bool(workflow.get("judge_agent_required"))
        for workflow in workflow_import.get("candidate_workflows", [])
    )
    workflow_import_safe = (
        workflow_import.get("import_status") == "imported_as_candidate_workflows"
        and not workflow_import.get("adopt_redthread_claims", {}).get("finding_created")
        and not workflow_import.get("adopt_redthread_claims", {}).get("severity_assigned")
        and not workflow_import.get("adopt_redthread_claims", {}).get("live_execution_authorized")
    )
    useful_delta_present = bool(local_status.get("used")) and (not empty_diff or local_observation_flag or observation_delta)
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "expect_useful_delta": bool(case["expect_useful_delta"]),
        "schema_accepted": bool(schema.get("passed")) and bool(local_status.get("used")),
        "fallback_used": bool(local_status.get("fallback_to_deterministic", True)),
        "local_llm_status": local_status.get("status", "unknown"),
        "empty_diff": empty_diff,
        "useful_delta_present": useful_delta_present,
        "local_observation_delta_claimed": local_observation_flag,
        "structured_subject_delta_present": observation_delta,
        "privacy_audit_passed": bool(privacy.get("passed")),
        "execution_candidate_present": execution_candidate_present,
        "next_redthread_action_clear": next_redthread_action_clear,
        "missing_context_clear": missing_context_clear,
        "candidate_has_observation_citations": candidate_has_observation_citations,
        "handoff_validation_passed": bool(handoff_validation.get("passed")),
        "handoff_useful": handoff_useful,
        "redthread_intent_evidence_importable": redthread_importable,
        "redthread_intent_evidence_validation_passed": bool(intent_evidence_validation.get("valid")),
        "candidate_workflow_created": candidate_workflow_created,
        "workflow_import_safe": workflow_import_safe,
        "product_proof_passed": product_proof_passed,
        "judge_required": judge_required,
        "forbidden_claim_count": forbidden_claim_count,
        "redthread_evaluation_required": bool(export.get("promotion_semantics", {}).get("redthread_evaluation_required")),
        "confirmed_finding_claimed": bool(export.get("promotion_semantics", {}).get("confirmed_security_finding_claimed")),
        "severity_claimed": bool(export.get("promotion_semantics", {}).get("severity_claimed")),
        "release_gate_override": bool(export.get("promotion_semantics", {}).get("release_gate_override")),
        "latency_seconds": round(elapsed, 3),
        "deterministic_output_dir": str(deterministic_dir),
        "local_output_dir": str(local_dir),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Local Intent Review Evaluation",
        "",
        f"- Cases: {report['summary']['case_count']}",
        f"- Local LLM accepted: {report['summary']['local_llm_accepted_count']}",
        f"- Fallback used: {report['summary']['fallback_count']}",
        f"- Useful deltas: {report['summary']['useful_delta_count']}",
        f"- Empty diffs: {report['summary']['empty_diff_count']}",
        f"- Privacy failures: {report['summary']['privacy_failure_count']}",
        f"- Forbidden claims: {report['summary']['forbidden_claim_count']}",
        f"- Useful handoffs: {report['summary']['handoff_useful_count']}",
        f"- RedThread importable cases: {report['summary']['redthread_importable_count']}",
        f"- Candidate workflow cases: {report['summary']['candidate_workflow_created_count']}",
        f"- Product proof passed: {report['summary']['product_proof_passed_count']}",
        "",
        "| Case | Local status | Fallback | Empty diff | Useful delta | Handoff useful | Importable | Product proof | Privacy |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in report.get("cases", []):
        lines.append(
            f"| `{case['case_id']}` | `{case['local_llm_status']}` | {case['fallback_used']} | {case['empty_diff']} | {case['useful_delta_present']} | {case['handoff_useful']} | {case['redthread_intent_evidence_importable']} | {case['product_proof_passed']} | {case['privacy_audit_passed']} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "- A technically successful local LLM run has `local status=accepted`, `fallback=False`, and passing privacy/schema guardrails.",
        "- Product value is shown by useful deltas on context-enriched cases, not by changing cautious baseline cases.",
        "- RedThread remains the final evaluator; this report does not claim findings, severity, scanner results, live execution proof, or release decisions.",
        "",
    ])
    return "\n".join(lines)


def evaluate_local_intent_review(
    batch_dir: str | Path,
    output_dir: str | Path,
    *,
    local_llm_cmd: str | None = None,
    boundary_rubric: str | None = None,
    reviewer_observations: str | None = None,
) -> dict[str, Any]:
    batch_dir = Path(batch_dir)
    output_dir = Path(output_dir)
    command = local_llm_cmd or os.environ.get("INTENT_REVIEW_LOCAL_LLM_CMD")
    cases = []
    old_cmd = os.environ.get("INTENT_REVIEW_LOCAL_LLM_CMD")
    if command:
        os.environ["INTENT_REVIEW_LOCAL_LLM_CMD"] = command
    try:
        for spec in _case_specs(boundary_rubric, reviewer_observations):
            case_root = output_dir / spec["case_id"]
            deterministic_dir = case_root / "deterministic"
            local_dir = case_root / "local_llm"
            common = {
                "boundary_rubric": spec.get("boundary_rubric"),
                "reviewer_observations": spec.get("reviewer_observations"),
            }
            build_sanitized_intent_review(batch_dir, deterministic_dir, agent_mode="deterministic", **common)
            start = time.monotonic()
            build_sanitized_intent_review(batch_dir, local_dir, agent_mode="auto", **common)
            cases.append(_summarize_case(spec, deterministic_dir, local_dir, time.monotonic() - start))
    finally:
        if old_cmd is None:
            os.environ.pop("INTENT_REVIEW_LOCAL_LLM_CMD", None)
        else:
            os.environ["INTENT_REVIEW_LOCAL_LLM_CMD"] = old_cmd

    summary = {
        "case_count": len(cases),
        "local_llm_accepted_count": sum(1 for c in cases if c["schema_accepted"]),
        "fallback_count": sum(1 for c in cases if c["fallback_used"]),
        "useful_delta_count": sum(1 for c in cases if c["useful_delta_present"]),
        "empty_diff_count": sum(1 for c in cases if c["empty_diff"]),
        "privacy_failure_count": sum(1 for c in cases if not c["privacy_audit_passed"]),
        "forbidden_claim_count": sum(int(c["forbidden_claim_count"]) for c in cases),
        "execution_candidate_present_count": sum(1 for c in cases if c["execution_candidate_present"]),
        "next_redthread_action_clear_count": sum(1 for c in cases if c["next_redthread_action_clear"]),
        "missing_context_clear_count": sum(1 for c in cases if c["missing_context_clear"]),
        "candidate_has_observation_citations_count": sum(1 for c in cases if c["candidate_has_observation_citations"]),
        "handoff_useful_count": sum(1 for c in cases if c["handoff_useful"]),
        "redthread_importable_count": sum(1 for c in cases if c["redthread_intent_evidence_importable"]),
        "intent_evidence_validation_passed_count": sum(1 for c in cases if c["redthread_intent_evidence_validation_passed"]),
        "candidate_workflow_created_count": sum(1 for c in cases if c["candidate_workflow_created"]),
        "workflow_import_safe_count": sum(1 for c in cases if c["workflow_import_safe"]),
        "product_proof_passed_count": sum(1 for c in cases if c["product_proof_passed"]),
        "judge_required_count": sum(1 for c in cases if c["judge_required"]),
    }
    report = {
        "schema_version": EVAL_SCHEMA_VERSION,
        "source_batch": str(batch_dir),
        "local_command_configured": bool(command),
        "redthread_final_gate_required": True,
        "summary": summary,
        "cases": cases,
    }
    _write_json(output_dir / "local_intent_review_eval.json", report)
    _write_text(output_dir / "local_intent_review_eval.md", render_markdown(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate default-auto local LLM intent review against deterministic review.")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--local-llm-cmd")
    parser.add_argument("--boundary-rubric")
    parser.add_argument("--reviewer-observations")
    args = parser.parse_args()
    report = evaluate_local_intent_review(
        args.batch_dir,
        args.output_dir,
        local_llm_cmd=args.local_llm_cmd,
        boundary_rubric=args.boundary_rubric,
        reviewer_observations=args.reviewer_observations,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
    empty_diff = deterministic_md == local_md
    deterministic_review = _read_json(deterministic_dir / "intent_review.json")
    local_review = _read_json(local_dir / "intent_review.json")
    observation_delta = deterministic_review.get("subjects", []) != local_review.get("subjects", [])
    local_observation_flag = any(
        bool(subject.get("local_model_observations", {}).get("useful_delta"))
        for subject in local_review.get("subjects", [])
    )
    forbidden_claim_count = int(privacy.get("forbidden_claim_language_hit_count", 0))
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
        "",
        "| Case | Local status | Fallback | Empty diff | Useful delta | Privacy |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for case in report.get("cases", []):
        lines.append(
            f"| `{case['case_id']}` | `{case['local_llm_status']}` | {case['fallback_used']} | {case['empty_diff']} | {case['useful_delta_present']} | {case['privacy_audit_passed']} |"
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

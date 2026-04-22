from __future__ import annotations

from typing import Any

from adapters.bridge.session_continuity import detect_candidate_header_bindings, session_continuity_note
from adapters.bridge.workflow_binding_inference import discover_candidate_bindings, discover_candidate_path_bindings


def discover_all_candidates(workflow_plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for workflow in workflow_plan.get("workflows", []):
        workflow_id = str(workflow.get("workflow_id", "unknown"))
        steps = sorted(workflow.get("steps", []), key=lambda s: int(s.get("workflow_step_index", 0)))
        pairs: list[dict[str, Any]] = []
        for i in range(len(steps) - 1):
            step_n = steps[i]
            step_n1 = steps[i + 1]
            source_case_id = str(step_n.get("case_id", ""))
            target_case_id = str(step_n1.get("case_id", ""))
            target_url = str(step_n1.get("request_url_template") or step_n1.get("path", "")).strip()
            candidate_path_bindings = (
                discover_candidate_path_bindings(None, target_url, source_case_id, target_case_id)
                if target_url
                else []
            )
            pairs.append(
                {
                    "source_case_id": source_case_id,
                    "target_case_id": target_case_id,
                    "candidate_bindings": [],
                    "candidate_path_bindings": candidate_path_bindings,
                }
            )
        result[workflow_id] = pairs
    return result


def discover_header_binding_pairs(workflow_plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        str(workflow.get("workflow_id", "unknown")): []
        for workflow in workflow_plan.get("workflows", [])
    }


def enrich_manifest_candidates(
    workflow_review_manifest: dict[str, Any],
    live_workflow_summary: dict[str, Any],
    cases: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    import copy

    result_by_step = {
        str(step_result.get("case_id", "")): step_result
        for workflow_result in live_workflow_summary.get("results", [])
        for step_result in workflow_result.get("results", [])
    }
    enriched_manifest = copy.deepcopy(workflow_review_manifest)
    all_enriched_candidates: list[dict[str, Any]] = []
    for workflow in enriched_manifest.get("workflows", []):
        for pair in workflow.get("candidate_binding_pairs", []):
            source_case_id = str(pair.get("source_case_id", ""))
            target_case_id = str(pair.get("target_case_id", ""))
            response_json = result_by_step.get(source_case_id, {}).get("response_json")
            target_step = next((s for s in workflow.get("steps", []) if str(s.get("case_id", "")) == target_case_id), {})
            if isinstance(response_json, dict):
                pair["candidate_bindings"] = discover_candidate_bindings(response_json, target_step, source_case_id, target_case_id)
            target_url = str(target_step.get("request_url_template") or target_step.get("path", "")).strip()
            if target_url:
                pair["candidate_path_bindings"] = discover_candidate_path_bindings(response_json, target_url, source_case_id, target_case_id)
            all_enriched_candidates.extend(pair.get("candidate_bindings", []) + pair.get("candidate_path_bindings", []))
        header_candidates = detect_candidate_header_bindings(workflow.get("steps", []), cases or {}, step_results=result_by_step)
        workflow["candidate_header_binding_pairs"] = header_candidates
        workflow["session_continuity_note"] = session_continuity_note(header_candidates)
        all_enriched_candidates.extend(header_candidates)
    enriched_manifest["candidate_binding_summary"] = candidate_summary(all_enriched_candidates)
    return enriched_manifest


def candidate_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    tier_counts: dict[str, int] = {}
    total = 0
    for candidate in candidates:
        tier = str(candidate.get("confidence_tier", "unknown"))
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        total += 1
    return {"total_candidate_count": total, "by_tier": tier_counts}


def session_note(candidates: list[dict[str, Any]]) -> str | None:
    return session_continuity_note(candidates)

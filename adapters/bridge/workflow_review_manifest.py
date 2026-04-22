from __future__ import annotations

from typing import Any

from adapters.bridge.workflow_binding_inference import (
    discover_candidate_bindings,
    discover_candidate_path_bindings,
)


def build_workflow_review_manifest(
    workflow_plan: dict[str, Any],
    live_workflow_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    results = _results_by_workflow(live_workflow_summary)
    review_artifacts = _artifacts_by_workflow(live_workflow_summary)
    candidate_pairs_by_workflow = _discover_all_candidates(workflow_plan)
    manifest_workflows = [
        _manifest_workflow(
            workflow,
            results.get(str(workflow.get("workflow_id", "unknown"))),
            review_artifacts.get(str(workflow.get("workflow_id", "unknown"))),
            candidate_pairs_by_workflow.get(str(workflow.get("workflow_id", "unknown")), []),
        )
        for workflow in workflow_plan.get("workflows", [])
    ]
    all_candidates = [
        candidate
        for workflow_pairs in candidate_pairs_by_workflow.values()
        for pair in workflow_pairs
        for candidate in pair.get("candidate_bindings", []) + pair.get("candidate_path_bindings", [])
    ]
    return {
        "plan_id": workflow_plan.get("plan_id", "unknown"),
        "workflow_count": workflow_plan.get("workflow_count", len(workflow_plan.get("workflows", []))),
        "workflow_requirement_summary": {} if live_workflow_summary is None else live_workflow_summary.get("workflow_requirement_summary", {}),
        "workflow_failure_class_summary": {} if live_workflow_summary is None else live_workflow_summary.get("workflow_failure_class_summary", {}),
        "reason_counts": {} if live_workflow_summary is None else live_workflow_summary.get("reason_counts", {}),
        "candidate_binding_summary": _candidate_summary(all_candidates),
        "workflows": manifest_workflows,
    }


def _manifest_workflow(
    workflow: dict[str, Any],
    result: dict[str, Any] | None,
    review_artifact: dict[str, Any] | None,
    candidate_pairs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
        "workflow_context_requirements": workflow.get("workflow_context_requirements", {}),
        "session_context_requirements": workflow.get("session_context_requirements", {}),
        "response_binding_contract": workflow.get("response_binding_contract", {}),
        "replay_status": None if result is None else result.get("status"),
        "failure_reason_code": None if result is None else result.get("failure_reason_code"),
        "failure_detail": None if result is None else result.get("failure_detail"),
        "binding_review_artifact": review_artifact or {"workflow_id": workflow.get("workflow_id", "unknown"), "steps": []},
        "candidate_binding_pairs": candidate_pairs or [],
        "steps": [
            {
                "case_id": step.get("case_id"),
                "workflow_step_index": step.get("workflow_step_index", 0),
                "step_context_requirements": step.get("step_context_requirements", {}),
                "response_bindings": step.get("response_bindings", []),
                "binding_review_summary": step.get("binding_review_summary", {}),
                "binding_review_decisions": step.get("binding_review_decisions", []),
            }
            for step in workflow.get("steps", [])
        ],
    }


def _results_by_workflow(live_workflow_summary: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if live_workflow_summary is None:
        return {}
    return {
        str(result.get("workflow_id", "unknown")): result
        for result in live_workflow_summary.get("results", [])
    }


def _artifacts_by_workflow(live_workflow_summary: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if live_workflow_summary is None:
        return {}
    return {
        str(artifact.get("workflow_id", "unknown")): artifact
        for artifact in live_workflow_summary.get("workflow_binding_review_artifacts", [])
    }


def _discover_all_candidates(
    workflow_plan: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Build candidate binding pairs for every workflow in the plan.

    For each consecutive step pair (N, N+1) in a workflow:
    - Run A1 candidate body binding discovery
    - Run A3 candidate path slot discovery

    Returns a dict keyed by workflow_id. Each value is a list of pair dicts:
      {
        "source_case_id": ...,
        "target_case_id": ...,
        "candidate_bindings": [...],    # A1
        "candidate_path_bindings": [...], # A3
      }

    Note: response JSON is not available at plan-build time (no live execution yet).
    The candidate discovery runs structurally against body templates and URL templates.
    When live replay results are present, callers may enrich this in the future.
    For now, we emit structural candidates only (i.e., based on the body schema and
    URL slots in the plan, paired against all scalar field names that would come from
    step N — represented here by a synthetic response skeleton derived from the plan).
    """
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

            # We don't have live response JSON at plan time.
            # Candidates will be enriched when live replay results are available.
            # Surface empty lists now — the structure is correct and ready for enrichment.
            candidate_bindings: list[dict[str, Any]] = []
            candidate_path_bindings: list[dict[str, Any]] = []

            # A3: URL slot matching is purely structural — we can run it now.
            target_url = str(
                step_n1.get("request_url_template")
                or step_n1.get("path", "")
            ).strip()
            if target_url:
                # For structural-only slot detection without live response JSON,
                # pass None — all slots will appear as "unmatched" in the manifest.
                candidate_path_bindings = discover_candidate_path_bindings(
                    None,
                    target_url,
                    source_case_id,
                    target_case_id,
                )

            pairs.append(
                {
                    "source_case_id": source_case_id,
                    "target_case_id": target_case_id,
                    "candidate_bindings": candidate_bindings,
                    "candidate_path_bindings": candidate_path_bindings,
                }
            )
        result[workflow_id] = pairs
    return result


def enrich_manifest_candidates(
    workflow_review_manifest: dict[str, Any],
    live_workflow_summary: dict[str, Any],
) -> dict[str, Any]:
    """Enrich candidate bindings using actual live response JSON from a completed replay.

    Called after live execution to replace structural-only candidates with
    response-data-aware candidates (A1 body matching with real response fields).

    Returns an updated manifest dict (does not mutate in place).
    """
    import copy
    result_by_step: dict[str, dict[str, Any]] = {}
    for workflow_result in live_workflow_summary.get("results", []):
        for step_result in workflow_result.get("results", []):
            case_id = str(step_result.get("case_id", ""))
            result_by_step[case_id] = step_result

    enriched_manifest = copy.deepcopy(workflow_review_manifest)
    all_enriched_candidates: list[dict[str, Any]] = []

    for workflow in enriched_manifest.get("workflows", []):
        for pair in workflow.get("candidate_binding_pairs", []):
            source_case_id = str(pair.get("source_case_id", ""))
            target_case_id = str(pair.get("target_case_id", ""))
            source_step_result = result_by_step.get(source_case_id, {})
            response_json = source_step_result.get("response_json")

            # Find the target step from the workflow steps
            target_step = next(
                (s for s in workflow.get("steps", []) if str(s.get("case_id", "")) == target_case_id),
                {},
            )

            # A1: enrich body binding candidates with real response JSON
            if isinstance(response_json, dict):
                pair["candidate_bindings"] = discover_candidate_bindings(
                    response_json,
                    target_step,
                    source_case_id,
                    target_case_id,
                )

            # A3: re-run path slot matching with real response JSON
            target_url = str(
                target_step.get("request_url_template")
                or target_step.get("path", "")
            ).strip()
            if target_url:
                pair["candidate_path_bindings"] = discover_candidate_path_bindings(
                    response_json,
                    target_url,
                    source_case_id,
                    target_case_id,
                )

            all_enriched_candidates.extend(
                pair.get("candidate_bindings", []) + pair.get("candidate_path_bindings", [])
            )

    enriched_manifest["candidate_binding_summary"] = _candidate_summary(all_enriched_candidates)
    return enriched_manifest


def _candidate_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a summary dict with counts grouped by confidence_tier."""
    tier_counts: dict[str, int] = {}
    total = 0
    for candidate in candidates:
        tier = str(candidate.get("confidence_tier", "unknown"))
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        total += 1
    return {
        "total_candidate_count": total,
        "by_tier": tier_counts,
    }

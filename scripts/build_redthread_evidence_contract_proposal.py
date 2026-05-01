from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_reviewer_packet import SENSITIVE_MARKERS

DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "redthread_evidence_contract_proposal"
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "redthread-evidence-contract-proposal.md"

PROPOSAL_VERSION = "redthread.evidence_contract_proposal.v0"


def build_redthread_evidence_contract_proposal(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    doc_path: str | Path | None = DEFAULT_DOC_PATH,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Write a tiny generic RedThread evidence-contract proposal without app-specific ingestion fields."""

    payload = _proposal_payload()
    markdown = _markdown(payload)
    audit = _configured_marker_check(markdown + json.dumps(payload, sort_keys=True))
    payload["configured_marker_check"] = audit
    if fail_on_marker_hit and audit["marker_hit_count"]:
        raise RuntimeError(f"contract proposal marker check failed with {audit['marker_hit_count']} hits")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "redthread_evidence_contract_proposal.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output_root / "redthread_evidence_contract_proposal.md").write_text(_markdown(payload), encoding="utf-8")
    if doc_path is not None:
        doc = Path(doc_path)
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _proposal_payload() -> dict[str, Any]:
    return {
        "schema_version": PROPOSAL_VERSION,
        "status": "proposal_only_not_upstreamed",
        "purpose": "Define the smallest generic evidence shape RedThread should own so adapters can supply sanitized workflow, replay, attack, and promotion evidence without app-specific ingestion names.",
        "ownership_split": {
            "redthread_should_own": [
                "generic evidence schema",
                "replay and dry-run evidence summaries",
                "promotion-gate recommendation semantics",
                "attack brief and rerun trigger vocabulary",
            ],
            "adapter_should_own": [
                "source ingestion",
                "source-specific fixture normalization",
                "local safety policy for approved execution context",
                "mapping source artifacts into the generic evidence contract",
            ],
        },
        "required_sections": _required_sections(),
        "promotion_recommendation": {
            "allowed_values": ["approve", "review", "block"],
            "semantics": {
                "approve": "ship candidate only for the tested evidence envelope",
                "review": "human review/change checkpoint before ship",
                "block": "do not ship from this run until blockers are resolved",
            },
            "must_not": [
                "treat replay/auth/context failure as a confirmed vulnerability",
                "turn write-capable workflows into approve without explicit safe context and review policy",
                "claim whole-application safety from one evidence envelope",
            ],
        },
        "privacy_rules": [
            "schema carries structural metadata, counts, labels, classes, and sanitized explanations only",
            "schema does not carry raw headers, cookies, sessions, request bodies, response bodies, secrets, or captured values",
            "artifact manifests may carry hashes and line/byte counts for sanitized artifacts",
        ],
        "acceptance_tests": [
            "consumer can explain why a run is approve/review/block without raw artifacts",
            "consumer can distinguish confirmed finding, auth/replay/context failure, and insufficient evidence",
            "consumer can identify next evidence to collect and rerun triggers",
            "schema contains no source-specific ingestion field names",
        ],
        "non_goals": [
            "new integration plumbing",
            "live-write expansion",
            "broad scanner wrapper",
            "full secret scanner",
            "upstream migration before reviewer comprehension is proven",
        ],
    }


def _required_sections() -> list[dict[str, Any]]:
    return [
        {
            "name": "evidence_envelope",
            "owner": "redthread",
            "fields": [
                "schema_version",
                "run_id",
                "input_family",
                "operation_count",
                "workflow_count",
                "artifact_manifest",
            ],
            "reason": "Pin what was tested and which sanitized artifacts were reviewed.",
        },
        {
            "name": "workflow_evidence",
            "owner": "redthread",
            "fields": [
                "ordered_operations",
                "workflow_classes",
                "successful_workflow_count",
                "blocked_workflow_count",
                "response_binding_summary",
                "binding_audit_summary",
            ],
            "reason": "Separate actual workflow proof from fixture-only or planning-only evidence; ordered_operations should carry sanitized sequence index, operation id, action class, method class, path template, and binding/input role labels.",
        },
        {
            "name": "attack_context_summary",
            "owner": "redthread",
            "fields": [
                "tool_action_schemas",
                "action_class_counts",
                "auth_model_label",
                "data_sensitivity_tags",
                "boundary_selector_classes",
                "dispatch_selector_classes",
                "field_role_summary",
                "targeted_missing_context_questions",
            ],
            "reason": "Give attack generation the minimum structural context needed for ownership, dispatch, auth, and data-sensitivity probes; tool_action_schemas should include action names/classes, required/optional parameter names, field roles, binding targets, and boundary-relevant field classes only.",
        },
        {
            "name": "replay_and_auth_diagnostics",
            "owner": "redthread",
            "fields": [
                "replay_passed",
                "dry_run_executed",
                "auth_delivery_label",
                "approved_auth_context_required",
                "approved_write_context_required",
                "replay_failure_category",
            ],
            "reason": "Explain auth/replay/context blocks without exposing credentials or sessions.",
        },
        {
            "name": "promotion_recommendation",
            "owner": "redthread",
            "fields": [
                "recommendation",
                "decision_reason_category",
                "confirmed_security_finding",
                "coverage_label",
                "coverage_gaps",
                "trusted_evidence",
                "not_proven",
            ],
            "reason": "Move generic approve/review/block recommendation semantics toward RedThread while keeping source ingestion outside the schema.",
        },
        {
            "name": "next_evidence_guidance",
            "owner": "redthread",
            "fields": [
                "top_targeted_probe",
                "next_evidence_needed",
                "rerun_triggers",
                "reviewer_action",
            ],
            "reason": "Tell a reviewer what to do next without requiring raw artifacts or repository knowledge.",
        },
    ]


def _configured_marker_check(text: str) -> dict[str, Any]:
    lowered = text.casefold()
    hit = any(marker.casefold() in lowered for marker in SENSITIVE_MARKERS)
    return {
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(SENSITIVE_MARKERS),
        "marker_hit_count": 1 if hit else 0,
        "passed": not hit,
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# RedThread Evidence Contract Proposal",
        "",
        f"Schema version: `{payload['schema_version']}`",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Purpose",
        "",
        payload["purpose"],
        "",
        "## Ownership split",
        "",
        "RedThread should own:",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["ownership_split"]["redthread_should_own"])
    lines.extend(["", "Adapters should own:", ""])
    lines.extend(f"- {item}" for item in payload["ownership_split"]["adapter_should_own"])
    lines.extend(["", "## Required generic sections", ""])
    for section in payload["required_sections"]:
        lines.extend(
            [
                f"### {section['name']}",
                "",
                f"- Owner: `{section['owner']}`",
                f"- Fields: `{','.join(section['fields'])}`",
                f"- Reason: {section['reason']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Promotion recommendation semantics",
            "",
            f"- Allowed values: `{','.join(payload['promotion_recommendation']['allowed_values'])}`",
        ]
    )
    for key, value in payload["promotion_recommendation"]["semantics"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "Must not:", ""])
    lines.extend(f"- {item}" for item in payload["promotion_recommendation"]["must_not"])
    lines.extend(["", "## Privacy rules", ""])
    lines.extend(f"- {item}" for item in payload["privacy_rules"])
    lines.extend(["", "## Acceptance tests", ""])
    lines.extend(f"- {item}" for item in payload["acceptance_tests"])
    lines.extend(["", "## Non-goals", ""])
    lines.extend(f"- {item}" for item in payload["non_goals"])
    if "configured_marker_check" in payload:
        audit = payload["configured_marker_check"]
        lines.extend(
            [
                "",
                "## Configured sensitive marker check",
                "",
                f"- Passed: `{audit['passed']}`",
                f"- Marker hits: `{audit['marker_hit_count']}`",
                f"- Marker set: `{audit['marker_set']}` (`{audit['marker_count']}` configured strings)",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a tiny generic RedThread evidence-contract proposal.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--doc-path", default=str(DEFAULT_DOC_PATH))
    parser.add_argument("--no-doc", action="store_true", help="Do not update the checked-in markdown proposal")
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if configured sensitive markers are present (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write outputs even when configured sensitive markers are present")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()

    proposal = build_redthread_evidence_contract_proposal(
        output_dir=args.output_dir,
        doc_path=None if args.no_doc else args.doc_path,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"redthread evidence contract proposal -> {Path(args.output_dir) / 'redthread_evidence_contract_proposal.md'}")
    print(json.dumps({
        "schema_version": proposal["schema_version"],
        "required_section_count": len(proposal["required_sections"]),
        "marker_hits": proposal["configured_marker_check"]["marker_hit_count"],
        "marker_check_passed": proposal["configured_marker_check"]["passed"],
    }, indent=2))


if __name__ == "__main__":
    main()

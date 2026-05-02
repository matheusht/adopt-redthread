from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_evidence_readiness import DEFAULT_OUTPUT_DIR as DEFAULT_READINESS_DIR
from scripts.build_evidence_readiness import build_evidence_readiness
from scripts.build_reviewer_packet import audit_sanitized_markdown

SCHEMA_VERSION = "adopt_redthread.evidence_remediation_queue.v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "evidence_remediation"
DEFAULT_READINESS = DEFAULT_READINESS_DIR / "evidence_readiness.json"
DEFAULT_DISTRIBUTION = REPO_ROOT / "runs" / "external_review_distribution" / "external_review_distribution_manifest.json"


def build_evidence_remediation_queue(
    *,
    readiness_ledger: str | Path = DEFAULT_READINESS,
    distribution_manifest: str | Path | None = DEFAULT_DISTRIBUTION,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    regenerate_readiness: bool = True,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Build an ordered queue of local evidence-loop remediation work.

    The queue translates sanitized readiness/distribution blockers into concrete
    next actions. It does not execute probes, does not contact reviewers, does
    not read raw app artifacts, and does not change approve/review/block verdict
    semantics.
    """

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    readiness_path = Path(readiness_ledger)
    distribution_path = Path(distribution_manifest) if distribution_manifest else None

    if regenerate_readiness:
        readiness = build_evidence_readiness(output_dir=readiness_path.parent, fail_on_marker_hit=fail_on_marker_hit)
        readiness_path = readiness_path.parent / "evidence_readiness.json"
    else:
        readiness = _load_json(readiness_path)
    distribution = _load_json(distribution_path) if distribution_path else {"schema_version": "not_configured"}

    input_paths = [path for path in (readiness_path, distribution_path) if path and path.exists()]
    input_audit = _safe_audit(audit_sanitized_markdown(input_paths))
    embedded_audits = _collect_marker_audits(readiness, distribution)
    marker_hit_count = input_audit["marker_hit_count"] + sum(int(audit.get("marker_hit_count", 0) or 0) for audit in embedded_audits)
    if fail_on_marker_hit and marker_hit_count:
        raise RuntimeError(f"evidence remediation queue marker audit failed with {marker_hit_count} hits")

    items = _queue_items(readiness, distribution)
    if marker_hit_count:
        items.insert(0, _privacy_item(marker_hit_count))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "queue_status": _queue_status(marker_hit_count, items),
        "artifact_policy": "The remediation queue is derived from sanitized readiness and distribution metadata only. It must not include raw captures, credentials, request/response bodies, source files, write-context values, raw boundary values, or reviewer free-form answers.",
        "source_readiness_status": readiness.get("readiness_status"),
        "source_distribution_status": distribution.get("distribution_status"),
        "item_count": len(items),
        "items": items,
        "input_marker_audit": input_audit,
        "embedded_marker_audits": embedded_audits,
        "commands": _commands(items),
        "non_claims": [
            "The remediation queue is not a release approval.",
            "The remediation queue is not external validation.",
            "The remediation queue is not boundary execution proof.",
            "The remediation queue does not prove buyer demand, production readiness, or whole-app safety.",
            "The remediation queue does not change local bridge approve/review/block verdict semantics.",
        ],
    }
    json_path = output_root / "evidence_remediation_queue.json"
    md_path = output_root / "evidence_remediation_queue.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")

    output_audit = _safe_audit(audit_sanitized_markdown([json_path, md_path]))
    if fail_on_marker_hit and output_audit["marker_hit_count"]:
        raise RuntimeError(f"evidence remediation queue output marker audit failed with {output_audit['marker_hit_count']} hits")
    payload["output_marker_audit"] = output_audit
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _queue_items(readiness: dict[str, Any], distribution: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    readiness_blockers = readiness.get("blockers", []) if isinstance(readiness.get("blockers"), list) else []
    for blocker in readiness_blockers:
        if not isinstance(blocker, dict):
            continue
        item = _item_for_readiness_blocker(blocker, readiness, distribution)
        if item:
            items.append(item)

    distribution_status = distribution.get("distribution_status")
    if distribution_status and distribution_status not in {"ready_to_distribute", "not_configured"}:
        items.append({
            "id": "distribution_manifest_not_ready",
            "priority": 15,
            "owner": "EvidencePackagingOwner",
            "status": "open",
            "source": "external_review_distribution_manifest",
            "blocked_by": ["fresh sanitized handoff/session artifacts"],
            "action": "Regenerate freshness, external review sessions, and the distribution manifest before sending reviewer folders.",
            "verification_commands": ["make evidence-freshness", "make evidence-external-review-distribution"],
            "acceptance_criteria": ["distribution_status is ready_to_distribute", "marker audits pass", "delivery count matches target review count"],
            "non_claim": "Distribution readiness is not external validation.",
        })

    deduped: dict[str, dict[str, Any]] = {}
    for item in items:
        existing = deduped.get(item["id"])
        if not existing or int(item["priority"]) < int(existing["priority"]):
            deduped[item["id"]] = item
    return sorted(deduped.values(), key=lambda item: (int(item["priority"]), str(item["id"])))


def _item_for_readiness_blocker(blocker: dict[str, Any], readiness: dict[str, Any], distribution: dict[str, Any]) -> dict[str, Any] | None:
    code = str(blocker.get("code"))
    if code == "external_validation_not_ready":
        readout = readiness.get("components", {}).get("external_validation_readout", {}) if isinstance(readiness.get("components"), dict) else {}
        target = readout.get("target_review_count") or 3
        complete = readout.get("complete_summary_count") or 0
        return {
            "id": "collect_external_reviewer_observations",
            "priority": 10,
            "owner": "ExternalValidationCoordinator",
            "status": "blocked_on_human_reviewers",
            "source": "evidence_readiness.external_validation_not_ready",
            "blocked_by": ["filled external reviewer observations", "sanitized observation summaries"],
            "action": f"Collect and summarize external reviewer observations until complete summaries reach {target}; current complete summaries: {complete}.",
            "verification_commands": _external_summary_commands(distribution),
            "acceptance_criteria": [
                f"complete sanitized summary count reaches {target}",
                "each summary is complete and marker-audit clean",
                "make evidence-external-validation-readout reports ready_for_external_validation_readout",
            ],
            "non_claim": "Missing external reviews mean waiting state, not validation failure or release approval.",
        }
    if code == "boundary_context_not_ready":
        return {
            "id": "validate_approved_boundary_context",
            "priority": 18,
            "owner": "BoundaryEvidenceOwner",
            "status": "blocked_on_approved_non_production_context",
            "source": "evidence_readiness.boundary_context_not_ready",
            "blocked_by": ["approved non-production tenant/user context", "safe actor scopes", "operator approval", "sanitized selector value references"],
            "action": "Generate or repair the sanitized boundary probe context until it reports ready_for_boundary_probe; do not execute probes or include raw actor, tenant, resource, credential, request, or response values.",
            "verification_commands": ["make evidence-boundary-context-request", "make evidence-boundary-probe-context BOUNDARY_CONTEXT=path/to/sanitized_context.json", "make evidence-readiness"],
            "acceptance_criteria": [
                "boundary context status is ready_for_boundary_probe before future execution is considered",
                "raw actor, tenant, resource, credential, request, and response values remain absent",
                "ready context is not treated as boundary execution proof",
            ],
            "non_claim": "Boundary context readiness authorizes only a future approved non-production probe path; it is not execution proof.",
        }
    if code == "boundary_probe_not_executed":
        context = readiness.get("components", {}).get("boundary_probe_context", {}) if isinstance(readiness.get("components"), dict) else {}
        context_ready = context.get("context_status") == "ready_for_boundary_probe"
        return {
            "id": "wait_for_approved_boundary_context" if not context_ready else "wait_for_boundary_probe_execution",
            "priority": 20,
            "owner": "BoundaryEvidenceOwner",
            "status": "blocked_on_approved_non_production_context" if not context_ready else "blocked_on_future_boundary_executor",
            "source": "evidence_readiness.boundary_probe_not_executed",
            "blocked_by": ["approved non-production tenant/user context", "safe actor scopes", "operator approval"] if not context_ready else ["future boundary executor", "approved non-production execution window", "sanitized boundary result"],
            "action": "Keep boundary execution blocked until approved non-production tenant/user context exists; validate sanitized context metadata before any future execution; do not treat blocked_missing_context as a confirmed vulnerability." if not context_ready else "Boundary context is ready, but no boundary probe has executed; do not treat ready context as execution proof or release approval.",
            "verification_commands": ["make evidence-boundary-context-request", "make evidence-boundary-probe-context", "make evidence-boundary-probe-result", "make evidence-readiness"],
            "acceptance_criteria": [
                "boundary result is produced from approved non-production context only",
                "raw actor, tenant, resource, credential, request, and response values remain absent",
                "confirmed_security_finding is true only for an actually failed boundary probe",
            ],
            "non_claim": "Boundary planning/context/result templates are not execution proof.",
        }
    if code in {"stale_or_missing_evidence_copies", "stale_or_missing_evidence"}:
        return {
            "id": "regenerate_stale_reviewer_evidence",
            "priority": 5,
            "owner": "EvidencePackagingOwner",
            "status": "open",
            "source": f"evidence_readiness.{code}",
            "blocked_by": ["fresh generated sanitized artifacts"],
            "action": "Regenerate reviewer packet, external handoff, external review sessions, freshness, and readiness before sharing evidence.",
            "verification_commands": [
                "make evidence-packet",
                "make evidence-external-review-handoff",
                "make evidence-external-review-sessions",
                "make evidence-freshness",
                "make evidence-readiness",
            ],
            "acceptance_criteria": ["freshness_status is fresh", "problem_count is 0", "marker audits pass"],
            "non_claim": "Fresh evidence copies are packaging integrity, not external validation.",
        }
    if code in {"missing_required_evidence", "invalid_required_evidence_schema"}:
        return {
            "id": "regenerate_required_evidence_artifacts",
            "priority": 1,
            "owner": "EvidencePackagingOwner",
            "status": "open",
            "source": f"evidence_readiness.{code}",
            "blocked_by": ["required sanitized generated artifacts"],
            "action": "Regenerate the required sanitized evidence artifacts until schemas are valid.",
            "verification_commands": [
                "make evidence-report",
                "make evidence-matrix",
                "make evidence-packet",
                "make evidence-external-review-handoff",
                "make evidence-external-review-sessions",
                "make evidence-external-validation-readout",
                "make evidence-boundary-probe-context",
                "make evidence-boundary-context-request",
                "make evidence-boundary-probe-result",
                "make evidence-readiness",
            ],
            "acceptance_criteria": ["all required components exist", "all required schemas are valid", "marker audits pass"],
            "non_claim": "Valid schemas make the local evidence loop readable; they do not approve release.",
        }
    if code == "privacy_marker_audit_failed":
        return _privacy_item(1)
    if code == "matrix_missing_decision_examples":
        return {
            "id": "restore_decision_example_coverage",
            "priority": 30,
            "owner": "EvidenceMatrixOwner",
            "status": "open",
            "source": "evidence_readiness.matrix_missing_decision_examples",
            "blocked_by": ["approve/review/block example generation"],
            "action": "Regenerate the evidence matrix with approve, review, and block examples present.",
            "verification_commands": ["make evidence-matrix", "make evidence-readiness"],
            "acceptance_criteria": ["matrix has approve, review, and block examples"],
            "non_claim": "Decision examples document semantics; they do not prove whole-app safety.",
        }
    return None


def _privacy_item(marker_hit_count: int) -> dict[str, Any]:
    return {
        "id": "resolve_privacy_marker_hits",
        "priority": 0,
        "owner": "PrivacyEvidenceOwner",
        "status": "privacy_blocked",
        "source": "marker_audits",
        "blocked_by": ["configured sensitive-marker hits"],
        "action": "Remove or regenerate marker-hit artifacts before sharing any reviewer evidence.",
        "verification_commands": ["make evidence-freshness", "make evidence-readiness", "make evidence-external-review-distribution", "make evidence-remediation-queue"],
        "acceptance_criteria": ["configured marker hit count is 0", "only sanitized metadata remains in generated evidence artifacts"],
        "non_claim": f"Privacy cleanup is required before review; marker_hit_count={marker_hit_count} is a packaging blocker, not a verdict semantic.",
    }


def _external_summary_commands(distribution: dict[str, Any]) -> list[str]:
    deliveries = distribution.get("deliveries", []) if isinstance(distribution.get("deliveries"), list) else []
    commands = [str(delivery.get("summary_command")) for delivery in deliveries if isinstance(delivery, dict) and delivery.get("summary_command")]
    commands.append("make evidence-external-review-returns")
    commands.append("make evidence-external-validation-readout")
    commands.append("make evidence-readiness")
    return commands


def _commands(items: list[dict[str, Any]]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for item in items:
        for command in item.get("verification_commands", []):
            if command not in seen:
                seen.add(command)
                commands.append(command)
    return commands


def _queue_status(marker_hit_count: int, items: list[dict[str, Any]]) -> str:
    if marker_hit_count:
        return "privacy_blocked"
    if not items:
        return "no_open_items"
    return "open_items"


def _collect_marker_audits(*payloads: dict[str, Any]) -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for label in (
            "input_marker_audit",
            "output_marker_audit",
            "sanitized_marker_audit",
            "marker_audits",
            "embedded_marker_audits",
        ):
            audit = payload.get(label)
            if isinstance(audit, dict):
                audits.append({"label": label, **audit})
            elif isinstance(audit, list):
                for entry in audit:
                    if isinstance(entry, dict):
                        audits.append({"label": label, **entry})
    return audits


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"schema_version": "not_configured"}
    if not path.exists():
        return {"schema_version": "missing", "load_error": "missing_file", "path": _display_path(path)}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": "invalid_json", "load_error": "invalid_json", "path": _display_path(path)}
    return loaded if isinstance(loaded, dict) else {"schema_version": "invalid_shape", "load_error": "json_not_object", "path": _display_path(path)}


def _safe_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "checked_files": audit.get("checked_files", []),
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(audit.get("markers_checked", [])) or audit.get("marker_count", 0),
        "marker_hit_count": audit.get("marker_hit_count", 0),
        "passed": audit.get("passed", False),
        "hit_files": sorted({str(hit.get("file")) for hit in audit.get("hits", []) if isinstance(hit, dict)}) or audit.get("hit_files", []),
    }


def _markdown(payload: dict[str, Any]) -> str:
    output_audit = payload.get("output_marker_audit", {"passed": "pending", "marker_hit_count": "pending"})
    lines = [
        "# Evidence Remediation Queue",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Queue status: `{payload['queue_status']}`",
        f"- Source readiness status: `{payload.get('source_readiness_status')}`",
        f"- Source distribution status: `{payload.get('source_distribution_status')}`",
        f"- Item count: `{payload['item_count']}`",
        "",
        "## Open items",
        "",
    ]
    if payload["items"]:
        for item in payload["items"]:
            lines.extend([
                f"### {item['priority']}. `{item['id']}`",
                "",
                f"- Owner: `{item['owner']}`",
                f"- Status: `{item['status']}`",
                f"- Source: `{item['source']}`",
                f"- Action: {item['action']}",
                f"- Blocked by: {', '.join(item.get('blocked_by', []))}",
                f"- Non-claim: {item['non_claim']}",
                "- Verification commands:",
            ])
            lines.extend(f"  - `{command}`" for command in item.get("verification_commands", []))
            lines.append("- Acceptance criteria:")
            lines.extend(f"  - {criterion}" for criterion in item.get("acceptance_criteria", []))
            lines.append("")
    else:
        lines.append("- none")
    lines.extend([
        "## Command queue",
        "",
    ])
    if payload["commands"]:
        lines.extend(f"- `{command}`" for command in payload["commands"])
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Marker audit",
        "",
        f"- Input marker audit passed: `{payload['input_marker_audit']['passed']}`",
        f"- Input marker hits: `{payload['input_marker_audit']['marker_hit_count']}`",
        f"- Output marker audit passed: `{output_audit['passed']}`",
        f"- Output marker hits: `{output_audit['marker_hit_count']}`",
        "",
        "## Non-claims",
        "",
    ])
    lines.extend(f"- {claim}" for claim in payload["non_claims"])
    lines.append("")
    return "\n".join(lines)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized evidence remediation queue from readiness/distribution metadata.")
    parser.add_argument("--readiness-ledger", default=str(DEFAULT_READINESS))
    parser.add_argument("--distribution-manifest", default=str(DEFAULT_DISTRIBUTION))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--skip-regenerate-readiness", action="store_true")
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if configured sensitive markers are present (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write the queue even when configured sensitive markers are present")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()
    payload = build_evidence_remediation_queue(
        readiness_ledger=args.readiness_ledger,
        distribution_manifest=args.distribution_manifest,
        output_dir=args.output_dir,
        regenerate_readiness=not args.skip_regenerate_readiness,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"evidence remediation queue -> {Path(args.output_dir) / 'evidence_remediation_queue.md'}")
    print(json.dumps({
        "queue_status": payload["queue_status"],
        "item_count": payload["item_count"],
        "commands": payload["commands"],
    }, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_reviewer_packet import (
    DEFAULT_OUTPUT_DIR as DEFAULT_PACKET_DIR,
    audit_handoff_completeness,
    audit_sanitized_markdown,
)

DEFAULT_REPORT = REPO_ROOT / "runs" / "reviewed_write_reference" / "evidence_report.md"
DEFAULT_MATRIX = REPO_ROOT / "runs" / "evidence_matrix" / "evidence_matrix.md"
DEFAULT_PACKET = DEFAULT_PACKET_DIR / "reviewer_packet.md"
DEFAULT_TEMPLATE = DEFAULT_PACKET_DIR / "reviewer_observation_template.md"
DEFAULT_BOUNDARY_RESULT = REPO_ROOT / "runs" / "boundary_probe_result" / "tenant_user_boundary_probe_result.md"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "external_review_handoff"
SCHEMA_VERSION = "adopt_redthread.external_review_handoff.v1"

CANONICAL_ARTIFACTS = {
    "evidence_report": "evidence_report.md",
    "evidence_matrix": "evidence_matrix.md",
    "reviewer_packet": "reviewer_packet.md",
    "reviewer_observation_template": "reviewer_observation_template.md",
    "boundary_probe_result": "tenant_user_boundary_probe_result.md",
}

FORBIDDEN_INPUTS = [
    "raw HAR files",
    "session material or credential values",
    "request or response bodies",
    "production or staging write-context values",
    "repo access, source files, terminal access, or operator walkthrough before silent answers",
]


def build_external_review_handoff(
    *,
    evidence_report: str | Path = DEFAULT_REPORT,
    evidence_matrix: str | Path = DEFAULT_MATRIX,
    reviewer_packet: str | Path = DEFAULT_PACKET,
    observation_template: str | Path = DEFAULT_TEMPLATE,
    boundary_probe_result: str | Path | None = DEFAULT_BOUNDARY_RESULT,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    target_review_count: int = 3,
    fail_on_marker_hit: bool = True,
    fail_on_incomplete_handoff: bool = True,
) -> dict[str, Any]:
    """Build a sanitized handoff directory for external human cold review.

    This packages only the reviewer-facing markdown artifacts and protocol notes.
    It does not summarize a completed review and must not be treated as validation
    until filled observations are summarized and rolled up separately.
    """

    sources = {
        "evidence_report": Path(evidence_report),
        "evidence_matrix": Path(evidence_matrix),
        "reviewer_packet": Path(reviewer_packet),
        "reviewer_observation_template": Path(observation_template),
    }
    boundary_result_path = Path(boundary_probe_result) if boundary_probe_result else None
    if boundary_result_path and boundary_result_path.exists():
        sources["boundary_probe_result"] = boundary_result_path
    missing = [name for name, path in sources.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing required handoff artifacts: {', '.join(missing)}")

    input_audit = audit_sanitized_markdown(list(sources.values()))
    if fail_on_marker_hit and input_audit["marker_hit_count"]:
        raise RuntimeError(f"external review input marker audit failed with {input_audit['marker_hit_count']} hits")

    completeness_audit = audit_handoff_completeness(sources["evidence_report"], sources["evidence_matrix"])
    if fail_on_incomplete_handoff and not completeness_audit["passed"]:
        raise RuntimeError(f"external review handoff completeness audit failed with {completeness_audit['missing_marker_count']} missing markers")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    for name, source in sources.items():
        destination = output_root / CANONICAL_ARTIFACTS[name]
        shutil.copyfile(source, destination)
        copied[name] = destination

    instructions = _instructions_markdown(target_review_count=target_review_count, include_boundary_result="boundary_probe_result" in sources)
    instructions_path = output_root / "external_reviewer_instructions.md"
    instructions_path.write_text(instructions, encoding="utf-8")

    output_audit = audit_sanitized_markdown([*copied.values(), instructions_path])
    if fail_on_marker_hit and output_audit["marker_hit_count"]:
        raise RuntimeError(f"external review output marker audit failed with {output_audit['marker_hit_count']} hits")

    manifest_path = output_root / "external_review_handoff_manifest.json"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "handoff_status": "ready_for_external_cold_review",
        "validation_status": "not_validation_until_filled_observations_are_summarized",
        "artifact_policy": "This directory contains only sanitized reviewer-facing markdown artifacts. Do not add raw captures, session material, credential values, request/response bodies, or staging write-context values.",
        "target_review_count": int(target_review_count),
        "artifacts": _artifact_manifest({**copied, "external_reviewer_instructions": instructions_path}),
        "protocol": {
            "allowed_artifacts": [CANONICAL_ARTIFACTS[name] for name in sources] + ["external_reviewer_instructions.md"],
            "forbidden_inputs": FORBIDDEN_INPUTS,
            "silent_review_required": True,
            "completion_rule": "A review counts only after the filled observation template is summarized with marker audit passed and complete=true.",
        },
        "next_commands": [
            "make evidence-observation-summary OBSERVATION=/path/to/filled_reviewer_observation_template.md OBSERVATION_OUTPUT=runs/reviewer_validation/review_1",
            "make evidence-validation-rollup SUMMARIES=\"/path/to/summary1.json /path/to/summary2.json /path/to/summary3.json\"",
        ],
        "input_marker_audit": _packet_safe_audit(input_audit),
        "output_marker_audit": _packet_safe_audit(output_audit),
        "handoff_completeness_audit": completeness_audit,
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    final_output_audit = audit_sanitized_markdown([*copied.values(), instructions_path, manifest_path])
    if fail_on_marker_hit and final_output_audit["marker_hit_count"]:
        raise RuntimeError(f"external review manifest marker audit failed with {final_output_audit['marker_hit_count']} hits")
    payload["output_marker_audit"] = _packet_safe_audit(final_output_audit)
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _artifact_manifest(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        manifest[name] = {
            "path": _display_path(path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "byte_count": len(data),
            "line_count": len(text.splitlines()),
        }
    return manifest


def _packet_safe_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "checked_files": audit["checked_files"],
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(audit.get("markers_checked", [])),
        "marker_hit_count": audit["marker_hit_count"],
        "passed": audit["passed"],
        "hit_files": sorted({hit["file"] for hit in audit["hits"]}),
    }


def _instructions_markdown(*, target_review_count: int, include_boundary_result: bool) -> str:
    forbidden = "\n".join(f"- {item}" for item in FORBIDDEN_INPUTS)
    optional_boundary = "- `tenant_user_boundary_probe_result.md`\n" if include_boundary_result else ""
    return f"""# External Human Cold-Review Instructions

Use this directory to run a silent external review of the sanitized evidence packet.

This is **not** validation by itself. It becomes validation evidence only after a reviewer fills `reviewer_observation_template.md`, the observation summary command marks it complete, and the configured sensitive-marker audit passes.

## Allowed files

- `evidence_report.md`
- `evidence_matrix.md`
- `reviewer_packet.md`
- `reviewer_observation_template.md`
{optional_boundary}- `external_reviewer_instructions.md`

## Forbidden inputs

{forbidden}

## Reviewer protocol

1. Give the reviewer only the allowed files above.
2. Do not explain the run before they answer the silent-review questions.
3. Ask them to decide ship, change, block, or unsure using only the evidence packet.
4. Ask them to fill `reviewer_observation_template.md` with judgments and sanitized evidence labels only.
5. Store each filled observation separately outside this handoff directory.
6. Summarize each filled observation with `make evidence-observation-summary`.
7. Roll up {target_review_count} complete summaries with `make evidence-validation-rollup`.

## Count rule

A review counts only when all of the following are true:

- observation summary `complete=true`
- observation summary marker audit passed
- release decision is recorded
- trusted evidence and weak/unclear evidence are recorded
- all six silent-review answers are present

Incomplete, walked-through, or marker-hit observations are not validation evidence.
"""


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized external human cold-review handoff directory.")
    parser.add_argument("--evidence-report", default=str(DEFAULT_REPORT))
    parser.add_argument("--evidence-matrix", default=str(DEFAULT_MATRIX))
    parser.add_argument("--reviewer-packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--observation-template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--boundary-probe-result", default=str(DEFAULT_BOUNDARY_RESULT), help="Optional sanitized boundary result markdown to copy if present")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--target-review-count", type=int, default=3)
    parser.add_argument("--fail-on-marker-hit", action="store_true", help="Exit non-zero if configured sensitive markers are present")
    parser.add_argument("--fail-on-incomplete-handoff", action="store_true", help="Exit non-zero if report/matrix handoff sections are missing")
    args = parser.parse_args()

    payload = build_external_review_handoff(
        evidence_report=args.evidence_report,
        evidence_matrix=args.evidence_matrix,
        reviewer_packet=args.reviewer_packet,
        observation_template=args.observation_template,
        boundary_probe_result=args.boundary_probe_result,
        output_dir=args.output_dir,
        target_review_count=args.target_review_count,
        fail_on_marker_hit=args.fail_on_marker_hit,
        fail_on_incomplete_handoff=args.fail_on_incomplete_handoff,
    )
    print(f"external review handoff -> {Path(args.output_dir)}")
    print(json.dumps({
        "handoff_status": payload["handoff_status"],
        "validation_status": payload["validation_status"],
        "artifact_count": len(payload["artifacts"]),
        "marker_hits": payload["output_marker_audit"]["marker_hit_count"],
        "handoff_complete": payload["handoff_completeness_audit"]["passed"],
    }, indent=2))


if __name__ == "__main__":
    main()

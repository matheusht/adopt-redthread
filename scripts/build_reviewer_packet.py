from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_evidence_matrix import DEFAULT_OUTPUT_DIR as DEFAULT_MATRIX_DIR
from scripts.build_evidence_matrix import DEFAULT_VICTORIA_EXPECTED, build_evidence_matrix
from scripts.build_evidence_report import build_evidence_report

DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "reviewer_packet"
DEFAULT_REPORT_RUN_DIR = REPO_ROOT / "runs" / "reviewed_write_reference"
DEFAULT_BOUNDARY_RESULT = REPO_ROOT / "runs" / "boundary_probe_result" / "tenant_user_boundary_probe_result.md"

SENSITIVE_MARKERS = (
    "value_preview",
    "set-cookie",
    "authorization:",
    "cookie:",
    "bearer ",
    "acct-123",
)

REVIEWER_QUESTIONS = (
    "Based on this evidence, would you ship, change, or block the release?",
    "What part of the decision did you trust most?",
    "What part was still unclear or too weak?",
    "Did the attack brief identify the next probe you would run?",
    "Did the evidence distinguish confirmed issue vs auth/replay failure vs insufficient evidence?",
    "Would you want this before every release of this agent/tool?",
)

OBSERVATION_FIELDS = (
    ("reviewer_role", "Reviewer role, e.g. security engineer, AI engineer, founder, or buyer."),
    ("release_decision", "Reviewer decision after reading only the packet artifacts: ship, change, block, or unsure."),
    ("trusted_evidence", "Evidence that most increased trust."),
    ("unclear_or_weak_evidence", "Evidence that remained confusing, weak, or missing."),
    ("next_probe_requested", "Next probe or rerun the reviewer wanted before release."),
    ("behavior_change", "Did the evidence change a ship/change/block decision, trigger a fix, or trigger a rerun request?"),
)

COLD_REVIEW_PROTOCOL = {
    "allowed_artifacts": [
        "evidence_report",
        "evidence_matrix",
        "reviewer_packet",
        "boundary_probe_result_if_present",
    ],
    "forbidden_inputs": [
        "raw HAR files",
        "session cookies or auth headers",
        "request or response bodies",
        "operator walkthrough before silent answers",
        "production/staging write context values",
    ],
    "steps": [
        "Give only the sanitized report, matrix, and packet to the reviewer.",
        "Ask the reviewer to answer the six silent-review questions before any explanation.",
        "Have the reviewer fill the observation template using judgments and evidence labels only.",
        "Run the observation summary command and treat incomplete output as non-validation evidence.",
    ],
    "success_criteria": [
        "Reviewer records ship/change/block or unsure without a walkthrough.",
        "Reviewer identifies trusted evidence and weak or unclear evidence.",
        "Reviewer names the next probe or explicitly says none is needed.",
        "Observation summary passes the configured sensitive-marker audit.",
    ],
}

REQUIRED_REPORT_MARKERS = (
    "## Reviewer quick read",
    "## Silent reviewer checklist",
    "## Next evidence to collect",
    "## Rerun triggers",
    "## Not proven by this run",
)

REQUIRED_MATRIX_MARKERS = (
    "Reviewer action",
    "Finding type",
    "Trusted evidence",
    "Next evidence needed",
    "Rerun triggers",
)


def build_reviewer_packet(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    report_run_dir: str | Path = DEFAULT_REPORT_RUN_DIR,
    matrix_output_dir: str | Path = DEFAULT_MATRIX_DIR,
    hero_run_dir: str | Path = REPO_ROOT / "runs" / "hero_binding_truth",
    reviewed_run_dir: str | Path = DEFAULT_REPORT_RUN_DIR,
    victoria_run_dir: str | Path = REPO_ROOT / "runs" / "victoria",
    victoria_expected: str | Path = DEFAULT_VICTORIA_EXPECTED,
    regenerate: bool = True,
    redthread_python: str | Path = REPO_ROOT.parent / "redthread" / ".venv" / "bin" / "python",
    redthread_src: str | Path = REPO_ROOT.parent / "redthread" / "src",
    boundary_probe_result: str | Path | None = DEFAULT_BOUNDARY_RESULT,
    fail_on_marker_hit: bool = False,
    fail_on_incomplete_handoff: bool = False,
) -> dict[str, Any]:
    """Build the reviewer handoff packet from the existing sanitized report and matrix surfaces."""
    build_evidence_matrix(
        output_dir=matrix_output_dir,
        hero_run_dir=hero_run_dir,
        reviewed_run_dir=reviewed_run_dir,
        victoria_run_dir=victoria_run_dir,
        victoria_expected=victoria_expected,
        regenerate=regenerate,
        redthread_python=redthread_python,
        redthread_src=redthread_src,
    )
    report_path = Path(report_run_dir) / "evidence_report.md"
    build_evidence_report(report_run_dir, report_path)
    return build_reviewer_packet_from_artifacts(
        evidence_report=report_path,
        evidence_matrix=Path(matrix_output_dir) / "evidence_matrix.md",
        boundary_probe_result=boundary_probe_result,
        output_dir=output_dir,
        fail_on_marker_hit=fail_on_marker_hit,
        fail_on_incomplete_handoff=fail_on_incomplete_handoff,
    )


def build_reviewer_packet_from_artifacts(
    *,
    evidence_report: str | Path,
    evidence_matrix: str | Path,
    boundary_probe_result: str | Path | None = DEFAULT_BOUNDARY_RESULT,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    fail_on_marker_hit: bool = False,
    fail_on_incomplete_handoff: bool = False,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = Path(evidence_report)
    matrix_path = Path(evidence_matrix)
    artifact_paths = {"evidence_report": report_path, "evidence_matrix": matrix_path}
    boundary_result_path = Path(boundary_probe_result) if boundary_probe_result else None
    if boundary_result_path and boundary_result_path.exists():
        artifact_paths["boundary_probe_result"] = boundary_result_path
    template_path = output_root / "reviewer_observation_template.md"
    audit = audit_sanitized_markdown(list(artifact_paths.values()))
    if fail_on_marker_hit and audit["marker_hit_count"]:
        raise RuntimeError(f"sanitized marker audit failed with {audit['marker_hit_count']} hits")
    completeness_audit = audit_handoff_completeness(report_path, matrix_path)
    if fail_on_incomplete_handoff and not completeness_audit["passed"]:
        raise RuntimeError(f"reviewer handoff completeness audit failed with {completeness_audit['missing_marker_count']} missing markers")
    packet_audit = _packet_safe_audit(audit)
    payload = {
        "schema_version": "adopt_redthread.reviewer_packet.v1",
        "artifact_policy": "Reviewer packet points only to sanitized markdown evidence. Raw HAR/session/cookie/header/body/run values stay ignored under runs/ and must not be copied into this packet.",
        "artifacts": {
            "evidence_report": _display_path(report_path),
            "evidence_matrix": _display_path(matrix_path),
            "reviewer_observation_template": _display_path(template_path),
            **({"boundary_probe_result": _display_path(boundary_result_path)} if boundary_result_path and boundary_result_path.exists() else {}),
        },
        "artifact_manifest": _artifact_manifest(artifact_paths),
        "reviewer_questions": list(REVIEWER_QUESTIONS),
        "decision_semantics": {
            "approve": "ship candidate for the tested evidence envelope; not a whole-app safety proof",
            "review": "human change/review checkpoint before ship, commonly for write-capable paths",
            "block": "do not ship from this run until required context, replay, or evidence blockers are resolved",
        },
        "cold_review_protocol": COLD_REVIEW_PROTOCOL,
        "sanitized_marker_audit": packet_audit,
        "handoff_completeness_audit": completeness_audit,
        "observation_template": _observation_template(),
    }
    packet_md = _markdown(payload)
    (output_root / "reviewer_packet.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output_root / "reviewer_packet.md").write_text(packet_md, encoding="utf-8")
    template_path.write_text(_observation_markdown(payload["observation_template"]), encoding="utf-8")
    return payload


def _artifact_manifest(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        if path.exists():
            data = path.read_bytes()
            text = data.decode("utf-8", errors="replace")
            manifest[name] = {
                "path": _display_path(path),
                "exists": True,
                "sha256": hashlib.sha256(data).hexdigest(),
                "byte_count": len(data),
                "line_count": len(text.splitlines()),
            }
        else:
            manifest[name] = {
                "path": _display_path(path),
                "exists": False,
                "sha256": None,
                "byte_count": 0,
                "line_count": 0,
            }
    return manifest



def _observation_template() -> dict[str, Any]:
    return {
        "schema_version": "adopt_redthread.reviewer_observation_template.v1",
        "instructions": "Use after the reviewer reads the packet artifacts without a walkthrough. Do not paste raw HAR, cookie, auth header, request body, response body, or secret values into answers.",
        "fields": [{"field": field, "prompt": prompt, "answer": ""} for field, prompt in OBSERVATION_FIELDS],
        "silent_reviewer_questions": [{"question": question, "answer": ""} for question in REVIEWER_QUESTIONS],
    }



def audit_handoff_completeness(evidence_report: str | Path, evidence_matrix: str | Path) -> dict[str, Any]:
    checks = {
        "evidence_report": {"path": _display_path(Path(evidence_report)), "required_markers": list(REQUIRED_REPORT_MARKERS)},
        "evidence_matrix": {"path": _display_path(Path(evidence_matrix)), "required_markers": list(REQUIRED_MATRIX_MARKERS)},
    }
    missing: list[dict[str, str]] = []
    for artifact, check in checks.items():
        path = Path(evidence_report) if artifact == "evidence_report" else Path(evidence_matrix)
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        for marker in check["required_markers"]:
            if marker not in text:
                missing.append({"artifact": artifact, "marker": marker})
    return {
        "checked_artifacts": {
            name: {"path": payload["path"], "required_marker_count": len(payload["required_markers"])}
            for name, payload in checks.items()
        },
        "missing_marker_count": len(missing),
        "passed": len(missing) == 0,
        "missing_markers": missing,
    }



def audit_sanitized_markdown(paths: list[str | Path]) -> dict[str, Any]:
    checked_files: list[str] = []
    hits: list[dict[str, str]] = []
    for raw_path in paths:
        path = Path(raw_path)
        checked_files.append(_display_path(path))
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        lowered = text.casefold()
        for marker in SENSITIVE_MARKERS:
            if marker.casefold() in lowered:
                hits.append({"file": _display_path(path), "marker": marker})
    return {
        "checked_files": checked_files,
        "markers_checked": list(SENSITIVE_MARKERS),
        "marker_hit_count": len(hits),
        "passed": len(hits) == 0,
        "hits": hits,
    }


def _packet_safe_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "checked_files": audit["checked_files"],
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(SENSITIVE_MARKERS),
        "marker_hit_count": audit["marker_hit_count"],
        "passed": audit["passed"],
        "hit_files": sorted({hit["file"] for hit in audit["hits"]}),
    }



def _markdown(payload: dict[str, Any]) -> str:
    audit = payload["sanitized_marker_audit"]
    completeness = payload["handoff_completeness_audit"]
    lines = [
        "# Reviewer Evidence Packet",
        "",
        payload["artifact_policy"],
        "",
        "## Open these sanitized artifacts",
        "",
        f"- Evidence report: `{payload['artifacts']['evidence_report']}`",
        f"- Evidence matrix: `{payload['artifacts']['evidence_matrix']}`",
        f"- Reviewer observation template: `{payload['artifacts']['reviewer_observation_template']}`",
        *([f"- Boundary probe result: `{payload['artifacts']['boundary_probe_result']}`"] if "boundary_probe_result" in payload["artifacts"] else ["- Boundary probe result: `absent; tenant_user_boundary_unproven wording remains driven by report/matrix coverage gaps`"]),
        "",
        "## Sanitized artifact manifest",
        "",
        "| Artifact | Lines | Bytes | SHA-256 |",
        "|---|---:|---:|---|",
    ]
    for name, artifact in payload["artifact_manifest"].items():
        lines.append(
            "| {name} | {line_count} | {byte_count} | `{sha256}` |".format(
                name=name,
                line_count=artifact["line_count"],
                byte_count=artifact["byte_count"],
                sha256=artifact["sha256"],
            )
        )
    lines.extend([
        "",
        "## Decision semantics",
        "",
        f"- `approve`: {payload['decision_semantics']['approve']}",
        f"- `review`: {payload['decision_semantics']['review']}",
        f"- `block`: {payload['decision_semantics']['block']}",
        "- Reviewer wording maps `ship` to `approve`, `change` to `review`, and `block` to `block`; do not infer `approve` from negated phrases such as `do not ship` or `cannot approve`.",
        "",
        "## Cold review protocol",
        "",
        "Allowed artifacts:",
        "",
    ])
    lines.extend(f"- `{artifact}`" for artifact in payload["cold_review_protocol"]["allowed_artifacts"])
    lines.extend([
        "",
        "Forbidden inputs:",
        "",
    ])
    lines.extend(f"- {item}" for item in payload["cold_review_protocol"]["forbidden_inputs"])
    lines.extend([
        "",
        "Steps:",
        "",
    ])
    lines.extend(f"{index}. {step}" for index, step in enumerate(payload["cold_review_protocol"]["steps"], start=1))
    lines.extend([
        "",
        "Success criteria:",
        "",
    ])
    lines.extend(f"- {item}" for item in payload["cold_review_protocol"]["success_criteria"])
    lines.extend([
        "",
        "## Silent reviewer questions",
        "",
    ])
    lines.extend(f"{index}. {question}" for index, question in enumerate(payload["reviewer_questions"], start=1))
    lines.extend(
        [
            "",
            "## Sanitized marker audit",
            "",
            f"- Passed: `{audit['passed']}`",
            f"- Marker hits: `{audit['marker_hit_count']}`",
            f"- Checked files: `{','.join(audit['checked_files'])}`",
            f"- Marker set: `{audit['marker_set']}` (`{audit['marker_count']}` configured strings)",
        ]
    )
    if audit["hit_files"]:
        lines.append("- Hit files: `{}`".format(",".join(audit["hit_files"])))
    else:
        lines.append("- Hit files: `none`")
    lines.extend(
        [
            "",
            "## Handoff completeness audit",
            "",
            f"- Passed: `{completeness['passed']}`",
            f"- Missing required markers: `{completeness['missing_marker_count']}`",
            f"- Checked artifacts: `{','.join(sorted(completeness['checked_artifacts']))}`",
            "",
            "## Handoff rule",
            "",
            "Give the report, matrix, and boundary result if present to the reviewer first. Do not explain the run until they answer the silent reviewer questions. Use the observation template only after they answer.",
            "",
            "After the reviewer fills the template, run `make evidence-observation-summary OBSERVATION=/path/to/filled_reviewer_observation_template.md` to produce the sanitized observation summary. Treat an incomplete summary as `incomplete_not_reviewer_evidence`, not as validation.",
            "",
        ]
    )
    return "\n".join(lines)



def _observation_markdown(template: dict[str, Any]) -> str:
    lines = [
        "# Reviewer Observation Template",
        "",
        template["instructions"],
        "",
        "## Review metadata",
        "",
    ]
    for field in template["fields"]:
        lines.extend([
            f"### {field['field']}",
            field["prompt"],
            "",
            "Answer:",
            "",
        ])
    lines.extend(["## Silent reviewer answers", ""])
    for index, question in enumerate(template["silent_reviewer_questions"], start=1):
        lines.extend([
            f"### Question {index}",
            question["question"],
            "",
            "Answer:",
            "",
        ])
    lines.extend([
        "## Sanitization rule",
        "",
        "Record only reviewer judgments and sanitized evidence labels. Do not paste raw captured values, session material, request bodies, response bodies, or secrets.",
        "",
    ])
    return "\n".join(lines)



def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized reviewer handoff packet for evidence review.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report-run-dir", default=str(DEFAULT_REPORT_RUN_DIR))
    parser.add_argument("--matrix-output-dir", default=str(DEFAULT_MATRIX_DIR))
    parser.add_argument("--hero-run-dir", default=str(REPO_ROOT / "runs" / "hero_binding_truth"))
    parser.add_argument("--reviewed-run-dir", default=str(DEFAULT_REPORT_RUN_DIR))
    parser.add_argument("--victoria-run-dir", default=str(REPO_ROOT / "runs" / "victoria"))
    parser.add_argument("--victoria-expected", default=str(DEFAULT_VICTORIA_EXPECTED))
    parser.add_argument("--use-existing", action="store_true", help="Do not regenerate deterministic approve/review matrix rows")
    parser.add_argument("--redthread-python", default=str(REPO_ROOT.parent / "redthread" / ".venv" / "bin" / "python"))
    parser.add_argument("--redthread-src", default=str(REPO_ROOT.parent / "redthread" / "src"))
    parser.add_argument("--boundary-probe-result", default=str(DEFAULT_BOUNDARY_RESULT), help="Optional sanitized boundary result markdown to include if present")
    parser.add_argument("--fail-on-marker-hit", action="store_true", help="Exit non-zero if generated markdown contains configured sensitive markers")
    parser.add_argument("--fail-on-incomplete-handoff", action="store_true", help="Exit non-zero if report/matrix do not contain required reviewer handoff sections")
    args = parser.parse_args()

    packet = build_reviewer_packet(
        output_dir=args.output_dir,
        report_run_dir=args.report_run_dir,
        matrix_output_dir=args.matrix_output_dir,
        hero_run_dir=args.hero_run_dir,
        reviewed_run_dir=args.reviewed_run_dir,
        victoria_run_dir=args.victoria_run_dir,
        victoria_expected=args.victoria_expected,
        regenerate=not args.use_existing,
        redthread_python=args.redthread_python,
        redthread_src=args.redthread_src,
        boundary_probe_result=args.boundary_probe_result,
        fail_on_marker_hit=args.fail_on_marker_hit,
        fail_on_incomplete_handoff=args.fail_on_incomplete_handoff,
    )
    print(f"reviewer packet -> {Path(args.output_dir) / 'reviewer_packet.md'}")
    print(json.dumps({
        "marker_hits": packet["sanitized_marker_audit"]["marker_hit_count"],
        "marker_audit_passed": packet["sanitized_marker_audit"]["passed"],
        "handoff_complete": packet["handoff_completeness_audit"]["passed"],
    }, indent=2))


if __name__ == "__main__":
    main()

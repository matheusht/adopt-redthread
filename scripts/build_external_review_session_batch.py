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

from scripts.build_reviewer_packet import audit_sanitized_markdown

DEFAULT_HANDOFF_DIR = REPO_ROOT / "runs" / "external_review_handoff"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "external_review_sessions"
SCHEMA_VERSION = "adopt_redthread.external_review_session_batch.v1"
HANDOFF_SCHEMA = "adopt_redthread.external_review_handoff.v1"


def build_external_review_session_batch(
    *,
    handoff_dir: str | Path = DEFAULT_HANDOFF_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    review_count: int = 3,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Create per-review external cold-review session folders from a sanitized handoff.

    This is scheduling/intake plumbing only. It copies the already-sanitized handoff
    artifacts into isolated reviewer folders and records the command path for later
    observation summarization. It does not create validation evidence and does not read
    raw captures, source files, or session material.
    """

    if review_count < 1:
        raise ValueError("review_count must be at least 1")

    handoff_root = Path(handoff_dir)
    manifest_path = handoff_root / "external_review_handoff_manifest.json"
    handoff_manifest = _load_handoff_manifest(manifest_path)
    allowed_artifacts = _allowed_artifacts(handoff_manifest)
    source_paths = {name: handoff_root / name for name in allowed_artifacts}
    missing = [name for name, path in source_paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing allowed handoff artifact(s): {', '.join(missing)}")

    input_audit = audit_sanitized_markdown([manifest_path, *source_paths.values()])
    if fail_on_marker_hit and input_audit["marker_hit_count"]:
        raise RuntimeError(f"external review session input marker audit failed with {input_audit['marker_hit_count']} hits")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    sessions: list[dict[str, Any]] = []
    generated_files: list[Path] = []
    for index in range(1, review_count + 1):
        session_id = f"review_{index}"
        session_dir = output_root / session_id
        artifact_dir = session_dir / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        copied = {}
        for name, source in source_paths.items():
            destination = artifact_dir / name
            shutil.copyfile(source, destination)
            copied[name] = destination
            generated_files.append(destination)

        observation_source = source_paths.get("reviewer_observation_template.md")
        filled_observation = session_dir / "filled_reviewer_observation.md"
        if observation_source:
            shutil.copyfile(observation_source, filled_observation)
            generated_files.append(filled_observation)

        instructions_path = session_dir / "reviewer_session_instructions.md"
        instructions_path.write_text(
            _session_instructions(
                session_id=session_id,
                allowed_artifacts=sorted(copied),
                filled_observation=filled_observation,
                expected_summary=session_dir / "reviewer_observation_summary.json",
            ),
            encoding="utf-8",
        )
        generated_files.append(instructions_path)
        sessions.append(
            {
                "session_id": session_id,
                "session_dir": _display_path(session_dir),
                "artifact_dir": _display_path(artifact_dir),
                "allowed_artifacts": {name: _artifact_record(path) for name, path in sorted(copied.items())},
                "filled_observation_path": _display_path(filled_observation),
                "expected_summary_path": _display_path(session_dir / "reviewer_observation_summary.json"),
                "summary_command": (
                    f"make evidence-observation-summary OBSERVATION={_display_path(filled_observation)} "
                    f"OBSERVATION_OUTPUT={_display_path(session_dir)}"
                ),
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "session_status": "ready_for_external_reviewer_distribution",
        "validation_status": "not_validation_until_filled_observations_are_summarized",
        "artifact_policy": "Session folders copy only sanitized external-handoff artifacts and a blank observation template. They must not include raw captures, auth/session material, request/response bodies, source files, or staging write-context values.",
        "handoff_manifest": _display_path(manifest_path),
        "handoff_schema_valid": handoff_manifest.get("schema_version") == HANDOFF_SCHEMA,
        "handoff_status": handoff_manifest.get("handoff_status", "unknown"),
        "target_review_count": int(review_count),
        "sessions": sessions,
        "rollup_command": _rollup_command(sessions),
        "input_marker_audit": _safe_audit(input_audit),
    }
    batch_json = output_root / "external_review_session_batch.json"
    batch_md = output_root / "external_review_session_batch.md"
    batch_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    batch_md.write_text(_markdown(payload), encoding="utf-8")
    generated_files.extend([batch_json, batch_md])

    output_audit = audit_sanitized_markdown(generated_files)
    if fail_on_marker_hit and output_audit["marker_hit_count"]:
        raise RuntimeError(f"external review session output marker audit failed with {output_audit['marker_hit_count']} hits")
    payload["output_marker_audit"] = _safe_audit(output_audit)
    batch_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    batch_md.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _load_handoff_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing external handoff manifest: {path}")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("external handoff manifest must be a JSON object")
    return loaded


def _allowed_artifacts(handoff_manifest: dict[str, Any]) -> list[str]:
    protocol = handoff_manifest.get("protocol", {}) if isinstance(handoff_manifest.get("protocol"), dict) else {}
    allowed = protocol.get("allowed_artifacts", []) if isinstance(protocol, dict) else []
    names = [str(name) for name in allowed if str(name).endswith(".md")]
    if not names:
        raise ValueError("external handoff manifest does not list markdown allowed_artifacts")
    return names


def _artifact_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    return {
        "path": _display_path(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_count": len(data),
        "line_count": len(text.splitlines()),
    }


def _safe_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "checked_files": audit["checked_files"],
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(audit.get("markers_checked", [])),
        "marker_hit_count": audit["marker_hit_count"],
        "passed": audit["passed"],
        "hit_files": sorted({hit["file"] for hit in audit["hits"]}),
    }


def _rollup_command(sessions: list[dict[str, Any]]) -> str:
    summaries = " ".join(session["expected_summary_path"] for session in sessions)
    return f"make evidence-validation-rollup SUMMARIES=\"{summaries}\""


def _session_instructions(*, session_id: str, allowed_artifacts: list[str], filled_observation: Path, expected_summary: Path) -> str:
    allowed = "\n".join(f"- `artifacts/{name}`" for name in allowed_artifacts)
    return f"""# External Review Session: {session_id}

Use this folder for one silent external cold review. This folder is not validation evidence until the filled observation is summarized and the summary is rolled up.

## Allowed files

{allowed}
- `{filled_observation.name}`

## Forbidden inputs

- raw HAR files
- session material or credential values
- request or response bodies
- production or staging write-context values
- repo access, source files, terminal access, or operator walkthrough before silent answers
- prior reviewer answers

## Reviewer steps

1. Open only the files listed above.
2. Answer the silent-review questions before any walkthrough.
3. Save sanitized answers in `{filled_observation.name}`.
4. Do not paste raw captured values, source code, session material, request bodies, response bodies, or credentials.
5. After the reviewer is done, summarize with:

```bash
make evidence-observation-summary OBSERVATION={_display_path(filled_observation)} OBSERVATION_OUTPUT={_display_path(expected_summary.parent)}
```

Expected summary path: `{_display_path(expected_summary)}`.
"""


def _markdown(payload: dict[str, Any]) -> str:
    output_audit = payload.get("output_marker_audit", {"passed": "pending", "marker_hit_count": "pending", "hit_files": []})
    lines = [
        "# External Review Session Batch",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Session status: `{payload['session_status']}`",
        f"- Validation status: `{payload['validation_status']}`",
        f"- Target review count: `{payload['target_review_count']}`",
        f"- Handoff manifest: `{payload['handoff_manifest']}`",
        f"- Handoff schema valid: `{payload['handoff_schema_valid']}`",
        f"- Handoff status: `{payload['handoff_status']}`",
        "",
        "## Sessions",
        "",
        "| Session | Directory | Filled observation | Expected summary |",
        "|---|---|---|---|",
    ]
    for session in payload["sessions"]:
        lines.append(
            f"| `{session['session_id']}` | `{session['session_dir']}` | `{session['filled_observation_path']}` | `{session['expected_summary_path']}` |"
        )
    lines.extend([
        "",
        "## Commands",
        "",
    ])
    for session in payload["sessions"]:
        lines.append(f"- `{session['summary_command']}`")
    lines.extend([
        f"- `{payload['rollup_command']}`",
        "",
        "## Count rule",
        "",
        "A session counts only after its filled observation is summarized, the summary is complete, and the configured sensitive-marker audit passes. Blank templates, walked-through reviews, and marker-hit observations are not validation evidence.",
        "",
        "## Marker audit",
        "",
        f"- Input marker audit passed: `{payload['input_marker_audit']['passed']}`",
        f"- Input marker hits: `{payload['input_marker_audit']['marker_hit_count']}`",
        f"- Output marker audit passed: `{output_audit['passed']}`",
        f"- Output marker hits: `{output_audit['marker_hit_count']}`",
        f"- Output hit files: `{','.join(output_audit.get('hit_files', [])) if output_audit.get('hit_files') else 'none'}`",
        "",
    ])
    return "\n".join(lines)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build isolated external cold-review session folders from a sanitized handoff.")
    parser.add_argument("--handoff-dir", default=str(DEFAULT_HANDOFF_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--review-count", type=int, default=3)
    parser.add_argument("--fail-on-marker-hit", action="store_true", help="Exit non-zero if configured sensitive markers are present")
    args = parser.parse_args()
    payload = build_external_review_session_batch(
        handoff_dir=args.handoff_dir,
        output_dir=args.output_dir,
        review_count=args.review_count,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"external review sessions -> {Path(args.output_dir)}")
    print(json.dumps({
        "session_status": payload["session_status"],
        "validation_status": payload["validation_status"],
        "session_count": len(payload["sessions"]),
        "marker_hits": payload["output_marker_audit"]["marker_hit_count"],
    }, indent=2))


if __name__ == "__main__":
    main()

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

DEFAULT_OBSERVATION_PATH = REPO_ROOT / "runs" / "reviewer_packet" / "reviewer_observation_template.md"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "reviewer_packet"

EXPECTED_FIELDS = (
    "reviewer_role",
    "release_decision",
    "trusted_evidence",
    "unclear_or_weak_evidence",
    "next_probe_requested",
    "behavior_change",
)

SILENT_QUESTION_KEYS = tuple(f"question_{index}" for index in range(1, 7))


def summarize_reviewer_observation(
    observation_path: str | Path = DEFAULT_OBSERVATION_PATH,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Summarize a filled reviewer observation template without copying raw run artifacts."""

    source = Path(observation_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8") if source.exists() else ""
    answers = _parse_answers(text)
    silent_answers = _parse_silent_answers(text)
    marker_audit = _observation_marker_audit(text)
    if fail_on_marker_hit and marker_audit["marker_hit_count"]:
        raise RuntimeError(f"reviewer observation marker audit failed with {marker_audit['marker_hit_count']} hits")

    payload = {
        "schema_version": "adopt_redthread.reviewer_observation_summary.v1",
        "source_observation": _display_path(source),
        "artifact_policy": "Summary contains reviewer judgments only. Do not paste raw HAR/session/cookie/auth/header/body/request/response values into reviewer observations.",
        "answers": answers,
        "silent_reviewer_answers": silent_answers,
        "completion_summary": _completion_summary(answers, silent_answers),
        "validation_signals": _validation_signals(answers, silent_answers),
        "confusion_summary": _confusion_summary(answers),
        "sanitized_marker_audit": marker_audit,
    }
    (output_root / "reviewer_observation_summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output_root / "reviewer_observation_summary.md").write_text(_markdown(payload), encoding="utf-8")
    return payload


def _parse_silent_answers(text: str) -> dict[str, str]:
    answers: dict[str, str] = {key: "" for key in SILENT_QUESTION_KEYS}
    current: str | None = None
    collecting = False
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer, collecting
        if current:
            answers[current] = _clean_answer(buffer)
        buffer = []
        collecting = False

    for line in text.splitlines():
        if line.startswith("### Question "):
            flush()
            raw = line.removeprefix("### Question ").strip().split()[0]
            key = f"question_{raw}" if raw.isdigit() else None
            current = key if key in answers else None
            continue
        if line.startswith("### ") or line.startswith("## "):
            flush()
            current = None
            continue
        if current is None:
            continue
        if line.strip().casefold() == "answer:":
            collecting = True
            buffer = []
            continue
        if collecting:
            buffer.append(line)
    flush()
    return answers


def _parse_answers(text: str) -> dict[str, str]:
    answers: dict[str, str] = {field: "" for field in EXPECTED_FIELDS}
    current: str | None = None
    collecting = False
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer, collecting
        if current:
            answers[current] = _clean_answer(buffer)
        buffer = []
        collecting = False

    for line in text.splitlines():
        if line.startswith("### "):
            flush()
            name = line[4:].strip()
            current = name if name in EXPECTED_FIELDS else None
            continue
        if line.startswith("## "):
            flush()
            current = None
            continue
        if current is None:
            continue
        if line.strip().casefold() == "answer:":
            collecting = True
            buffer = []
            continue
        if collecting:
            buffer.append(line)
    flush()
    return answers


def _clean_answer(lines: list[str]) -> str:
    cleaned = "\n".join(lines).strip()
    return " ".join(cleaned.split())


def _completion_summary(answers: dict[str, str], silent_answers: dict[str, str]) -> dict[str, Any]:
    answered = [field for field in EXPECTED_FIELDS if answers.get(field)]
    missing = [field for field in EXPECTED_FIELDS if not answers.get(field)]
    answered_questions = [key for key in SILENT_QUESTION_KEYS if silent_answers.get(key)]
    missing_questions = [key for key in SILENT_QUESTION_KEYS if not silent_answers.get(key)]
    complete = len(missing) == 0 and len(missing_questions) == 0
    return {
        "expected_field_count": len(EXPECTED_FIELDS),
        "answered_field_count": len(answered),
        "missing_field_count": len(missing),
        "missing_fields": missing,
        "expected_silent_question_count": len(SILENT_QUESTION_KEYS),
        "answered_silent_question_count": len(answered_questions),
        "missing_silent_question_count": len(missing_questions),
        "missing_silent_questions": missing_questions,
        "complete": complete,
        "observation_status": "ready_for_review_signal" if complete else "incomplete_not_reviewer_evidence",
    }


def _validation_signals(answers: dict[str, str], silent_answers: dict[str, str]) -> dict[str, Any]:
    metadata_decision = _first_decision_label(answers.get("release_decision", ""))
    question_1_decision = _first_decision_label(silent_answers.get("question_1", ""))
    decision = metadata_decision if metadata_decision != "unrecorded" else question_1_decision
    behavior = answers.get("behavior_change", "")
    next_probe = answers.get("next_probe_requested", "")
    decision_consistency = _decision_consistency(metadata_decision, question_1_decision)
    return {
        "release_decision": decision,
        "metadata_release_decision": metadata_decision,
        "silent_question_1_decision": question_1_decision,
        "decision_consistency": decision_consistency,
        "decision_consistent": decision_consistency == "consistent",
        "behavior_change_recorded": bool(behavior),
        "next_probe_requested": bool(next_probe),
        "trusted_evidence_recorded": bool(answers.get("trusted_evidence", "")),
        "unclear_or_weak_evidence_recorded": bool(answers.get("unclear_or_weak_evidence", "")),
        "wants_repeat_review": _contains_any(" ".join([*answers.values(), *silent_answers.values()]), {"before every release", "every release", "again before", "rerun"}),
    }


def _confusion_summary(answers: dict[str, str]) -> dict[str, Any]:
    unclear = answers.get("unclear_or_weak_evidence", "")
    return {
        "has_confusion_or_weakness": bool(unclear),
        "unclear_or_weak_evidence": unclear or "none recorded",
        "next_probe_requested": answers.get("next_probe_requested", "") or "none recorded",
    }


def _decision_consistency(metadata_decision: str, question_1_decision: str) -> str:
    if metadata_decision == "unrecorded" or question_1_decision == "unrecorded":
        return "not_applicable"
    if metadata_decision == question_1_decision:
        return "consistent"
    return "inconsistent"


def _first_decision_label(value: str) -> str:
    lowered = value.casefold()
    if any(phrase in lowered for phrase in ("do not ship", "don't ship", "cannot ship", "can't ship")):
        return "block"
    if any(phrase in lowered for phrase in ("not approve", "cannot approve", "can't approve", "do not approve", "don't approve")):
        return "review"
    if "block" in lowered:
        return "block"
    if "review" in lowered or "change" in lowered:
        return "review"
    if "approve" in lowered or "ship" in lowered:
        return "approve"
    if "unsure" in lowered:
        return "unsure"
    return "unrecorded"


def _contains_any(value: str, needles: set[str]) -> bool:
    lowered = value.casefold()
    return any(needle in lowered for needle in needles)


def _observation_marker_audit(text: str) -> dict[str, Any]:
    lowered = text.casefold()
    hit_sections: list[str] = []
    for marker in SENSITIVE_MARKERS:
        if marker.casefold() in lowered:
            hit_sections.append("reviewer_observation")
    hit_sections = sorted(set(hit_sections))
    return {
        "marker_set": "configured_sensitive_marker_set",
        "marker_count": len(SENSITIVE_MARKERS),
        "marker_hit_count": len(hit_sections),
        "passed": len(hit_sections) == 0,
        "hit_sections": hit_sections,
    }


def _markdown(payload: dict[str, Any]) -> str:
    completion = payload["completion_summary"]
    signals = payload["validation_signals"]
    confusion = payload["confusion_summary"]
    audit = payload["sanitized_marker_audit"]
    silent_answers = payload["silent_reviewer_answers"]
    lines = [
        "# Reviewer Observation Summary",
        "",
        payload["artifact_policy"],
        "",
        "## Source",
        "",
        f"- Observation file: `{payload['source_observation']}`",
        "",
        "## Completion",
        "",
        f"- Complete: `{completion['complete']}`",
        f"- Observation status: `{completion['observation_status']}`",
        "- Reviewer signal: `captured`" if completion["complete"] else "- Reviewer signal: `none_captured_do_not_use_as_validation`",
        f"- Answered metadata fields: `{completion['answered_field_count']}/{completion['expected_field_count']}`",
        f"- Missing metadata fields: `{','.join(completion['missing_fields']) if completion['missing_fields'] else 'none'}`",
        f"- Answered silent questions: `{completion['answered_silent_question_count']}/{completion['expected_silent_question_count']}`",
        f"- Missing silent questions: `{','.join(completion['missing_silent_questions']) if completion['missing_silent_questions'] else 'none'}`",
        "",
        "## Validation signals",
        "",
        f"- Release decision: `{signals['release_decision']}`",
        f"- Metadata decision: `{signals['metadata_release_decision']}`",
        f"- Silent question 1 decision: `{signals['silent_question_1_decision']}`",
        f"- Decision consistency: `{signals['decision_consistency']}`",
        f"- Behavior change recorded: `{signals['behavior_change_recorded']}`",
        f"- Next probe requested: `{signals['next_probe_requested']}`",
        f"- Trusted evidence recorded: `{signals['trusted_evidence_recorded']}`",
        f"- Weak/unclear evidence recorded: `{signals['unclear_or_weak_evidence_recorded']}`",
        f"- Wants repeat review: `{signals['wants_repeat_review']}`",
        "",
        "## Silent reviewer answer summary",
        "",
    ]
    for key in SILENT_QUESTION_KEYS:
        lines.append(f"- {key}: {silent_answers.get(key) or 'not recorded'}")
    lines.extend([
        "",
        "## Confusion summary",
        "",
        f"- Has confusion or weak evidence: `{confusion['has_confusion_or_weakness']}`",
        f"- Unclear or weak evidence: {confusion['unclear_or_weak_evidence']}",
        f"- Next probe requested: {confusion['next_probe_requested']}",
        "",
        "## Configured sensitive marker check",
        "",
        f"- Passed: `{audit['passed']}`",
        f"- Marker hits: `{audit['marker_hit_count']}`",
        f"- Marker set: `{audit['marker_set']}` (`{audit['marker_count']}` configured strings)",
        "",
    ])
    return "\n".join(lines)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a filled reviewer observation template without raw artifacts.")
    parser.add_argument("--observation", default=str(DEFAULT_OBSERVATION_PATH), help="Filled reviewer_observation_template.md path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if the observation contains configured sensitive markers (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write the summary even when configured sensitive markers are present")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()

    summary = summarize_reviewer_observation(
        args.observation,
        output_dir=args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"reviewer observation summary -> {Path(args.output_dir) / 'reviewer_observation_summary.md'}")
    print(json.dumps({
        "complete": summary["completion_summary"]["complete"],
        "observation_status": summary["completion_summary"]["observation_status"],
        "release_decision": summary["validation_signals"]["release_decision"],
        "decision_consistency": summary["validation_signals"]["decision_consistency"],
        "marker_hits": summary["sanitized_marker_audit"]["marker_hit_count"],
        "marker_audit_passed": summary["sanitized_marker_audit"]["passed"],
    }, indent=2))


if __name__ == "__main__":
    main()

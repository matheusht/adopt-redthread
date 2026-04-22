from __future__ import annotations

# ---------------------------------------------------------------------------
# Phase B1 — Set-Cookie Response Detection
# Phase B2 — Session Continuity Contract
#
# Detects when a step's HTTP response sets a cookie that a subsequent step
# is expected to forward, and emits candidate_header_binding proposals into
# the review manifest.
#
# Design invariant: Machine proposes. Human approves. Engine replays cleanly.
# Candidates are proposals only — never applied automatically.
# ---------------------------------------------------------------------------

import re
from typing import Any


# ---------------------------------------------------------------------------
# Cookie header parsing
# ---------------------------------------------------------------------------

_COOKIE_NAME_RE = re.compile(r"^\s*([^=;,\s]+)\s*=")

# Header names of interest
_SET_COOKIE_HEADER = "set-cookie"
_COOKIE_HEADER = "cookie"


def parse_set_cookie_names(set_cookie_value: str) -> list[str]:
    """Parse one or more cookie names from a Set-Cookie header value.

    A single Set-Cookie header describes one cookie: "name=value; Path=/; ...".
    Multiple Set-Cookie headers may be present in a response (one per header line).
    This function handles one header value at a time.

    Returns a list with one element on success, or an empty list on failure.
    """
    match = _COOKIE_NAME_RE.match(set_cookie_value)
    if match:
        return [match.group(1).strip()]
    return []


def parse_all_set_cookie_names(response_headers: dict[str, str | list[str]]) -> list[str]:
    """Extract all cookie names from all Set-Cookie headers in a response.

    response_headers may map header names (case-insensitive) to either a string
    or a list of strings (for multi-value headers).

    Returns a de-duplicated list of cookie names, in encounter order.
    """
    names: list[str] = []
    seen: set[str] = set()

    def _process(value: str) -> None:
        for name in parse_set_cookie_names(value):
            if name not in seen:
                names.append(name)
                seen.add(name)

    for header_name, header_value in response_headers.items():
        if str(header_name).lower() != _SET_COOKIE_HEADER:
            continue
        if isinstance(header_value, list):
            for v in header_value:
                _process(str(v))
        else:
            _process(str(header_value))

    return names



def _step_sends_cookie_header(step_case: dict[str, Any], cookie_name: str) -> bool:
    """Return True if the case's request_blueprint sends a cookie header
    that references the given cookie name (by name presence or as a placeholder).
    """
    blueprint = step_case.get("request_blueprint", {})
    headers: dict[str, str] = blueprint.get("headers", {}) or {}
    for header_name, header_value in headers.items():
        if str(header_name).lower() != _COOKIE_HEADER:
            continue
        value_str = str(header_value)
        # Matches if cookie name appears literally or as a {{name}} placeholder
        if cookie_name in value_str or f"{{{{{cookie_name}}}}}" in value_str:
            return True
    # Also check write-context-style placeholder patterns in request_blueprint
    header_names: list[str] = blueprint.get("header_names", [])
    if _COOKIE_HEADER in {str(n).lower() for n in header_names}:
        # The step sends a cookie header — treat as a candidate regardless of value
        return True
    return False


# ---------------------------------------------------------------------------
# B1 Core: detect_candidate_header_bindings
# ---------------------------------------------------------------------------

def detect_candidate_header_bindings(
    steps: list[dict[str, Any]],
    cases: dict[str, dict[str, Any]],
    step_results: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Detect candidate header bindings arising from Set-Cookie / Cookie pairs.

    Parameters
    ----------
    steps:
        Ordered list of workflow step dicts (as they appear in workflow_plan).
    cases:
        Dict of case_id -> full case dict (from attack_plan).
    step_results:
        Optional dict of case_id -> step result dict (from live replay).
        When provided, `response_headers` is read from the result.
        When None, no response data is available (plan-time structural call)
        and the function returns an empty list.

    Returns a list of candidate_header_binding dicts, one per
    (source_step, cookie_name, target_step) triple found.

    Each candidate:
    {
        "source_case_id": str,
        "source_header": "set-cookie",
        "cookie_name": str,
        "target_case_id": str | None,   # None when no downstream user found
        "target_header": "cookie",
        "confidence_tier": "exact_name_match" | "unmatched",
        "reason": str,
        "candidate_type": "header_cookie_binding",
    }
    """
    if step_results is None:
        # No live data — structural call, nothing to discover yet
        return []

    sorted_steps = sorted(steps, key=lambda s: int(s.get("workflow_step_index", 0)))
    candidates: list[dict[str, Any]] = []

    for i, step in enumerate(sorted_steps):
        source_case_id = str(step.get("case_id", ""))
        result = step_results.get(source_case_id, {})
        response_headers: dict[str, Any] = result.get("response_headers", {}) or {}

        cookie_names = parse_all_set_cookie_names(response_headers)
        if not cookie_names:
            continue

        # For each cookie name in the set-cookie response, search downstream steps
        for cookie_name in cookie_names:
            matched_targets: list[str] = []
            for downstream_step in sorted_steps[i + 1:]:
                downstream_case_id = str(downstream_step.get("case_id", ""))
                downstream_case = cases.get(downstream_case_id, {})
                if _step_sends_cookie_header(downstream_case, cookie_name):
                    matched_targets.append(downstream_case_id)

            if matched_targets:
                for target_case_id in matched_targets:
                    candidates.append(
                        {
                            "source_case_id": source_case_id,
                            "source_header": _SET_COOKIE_HEADER,
                            "cookie_name": cookie_name,
                            "target_case_id": target_case_id,
                            "target_header": _COOKIE_HEADER,
                            "confidence_tier": "exact_name_match",
                            "reason": f"exact_name_match:{_SET_COOKIE_HEADER}:{cookie_name}->{_COOKIE_HEADER}",
                            "candidate_type": "header_cookie_binding",
                        }
                    )
            else:
                # Cookie was set but no downstream step was found that uses it —
                # still emit so the operator can see a session rotation event
                candidates.append(
                    {
                        "source_case_id": source_case_id,
                        "source_header": _SET_COOKIE_HEADER,
                        "cookie_name": cookie_name,
                        "target_case_id": None,
                        "target_header": _COOKIE_HEADER,
                        "confidence_tier": "unmatched",
                        "reason": f"unmatched:{_SET_COOKIE_HEADER}:{cookie_name}:no_downstream_user",
                        "candidate_type": "header_cookie_binding",
                    }
                )

    return candidates


# ---------------------------------------------------------------------------
# B2: session_continuity_note
# ---------------------------------------------------------------------------

def session_continuity_note(candidates: list[dict[str, Any]]) -> str | None:
    """Format a human-readable session continuity note from a list of candidates.

    Returns None when there are no candidates.
    Returns a compact note string listing each matched binding, e.g.:
      "step_a response sets cookie 'session'; step_b candidate header binding required"
    Multiple pairs are joined with " | ".
    """
    if not candidates:
        return None

    matched = [c for c in candidates if c.get("confidence_tier") != "unmatched"]
    unmatched = [c for c in candidates if c.get("confidence_tier") == "unmatched"]

    parts: list[str] = []
    for c in matched:
        parts.append(
            f"{c['source_case_id']} response sets cookie '{c['cookie_name']}'; "
            f"{c['target_case_id']} candidate header binding required"
        )
    for c in unmatched:
        parts.append(
            f"{c['source_case_id']} response sets cookie '{c['cookie_name']}'; "
            f"no downstream step found — operator review needed"
        )
    return " | ".join(parts) if parts else None

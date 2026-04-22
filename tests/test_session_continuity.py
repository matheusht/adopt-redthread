"""Tests for Phase B: Session Continuity Detection.

Covers:
  B1 — parse_set_cookie_names / parse_all_set_cookie_names
  B1 — detect_candidate_header_bindings (set-cookie → cookie)
  B2 — session_continuity_note formatter
  Manifest integration — candidate_header_binding_pairs + session_continuity_note
  Safety invariant — header candidates never in response_bindings
"""

from __future__ import annotations

import unittest

from adapters.bridge.session_continuity import (
    detect_candidate_header_bindings,
    parse_all_set_cookie_names,
    parse_set_cookie_names,
    session_continuity_note,
)
from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.bridge.workflow_review_manifest import (
    build_workflow_review_manifest,
    enrich_manifest_candidates,
)


# ---------------------------------------------------------------------------
# parse_set_cookie_names
# ---------------------------------------------------------------------------


class ParseSetCookieNamesTests(unittest.TestCase):

    def test_simple_cookie(self) -> None:
        names = parse_set_cookie_names("session=abc123; Path=/; HttpOnly")
        self.assertEqual(names, ["session"])

    def test_cookie_with_secure_prefix(self) -> None:
        names = parse_set_cookie_names("__Secure-next-auth.session-token=xyz; Secure; HttpOnly")
        self.assertEqual(names, ["__Secure-next-auth.session-token"])

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(parse_set_cookie_names(""), [])

    def test_cookie_without_value(self) -> None:
        # Edge case: header without = sign
        self.assertEqual(parse_set_cookie_names("sessiononly"), [])

    def test_cookie_with_spaces(self) -> None:
        names = parse_set_cookie_names("  token = value123 ; Path=/")
        self.assertEqual(names, ["token"])


class ParseAllSetCookieNamesTests(unittest.TestCase):

    def test_single_set_cookie_header(self) -> None:
        headers = {"set-cookie": "session=abc; Path=/"}
        names = parse_all_set_cookie_names(headers)
        self.assertIn("session", names)

    def test_case_insensitive_header_name(self) -> None:
        headers = {"Set-Cookie": "token=xyz; Secure"}
        names = parse_all_set_cookie_names(headers)
        self.assertIn("token", names)

    def test_no_set_cookie_headers(self) -> None:
        headers = {"content-type": "application/json"}
        names = parse_all_set_cookie_names(headers)
        self.assertEqual(names, [])

    def test_list_value_multiple_cookies(self) -> None:
        headers = {"set-cookie": ["session=abc; Path=/", "csrf=xyz; HttpOnly"]}
        names = parse_all_set_cookie_names(headers)
        self.assertIn("session", names)
        self.assertIn("csrf", names)
        self.assertEqual(len(names), 2)

    def test_no_duplicate_names(self) -> None:
        headers = {"set-cookie": ["session=abc", "session=def"]}
        names = parse_all_set_cookie_names(headers)
        self.assertEqual(names.count("session"), 1)


# ---------------------------------------------------------------------------
# detect_candidate_header_bindings
# ---------------------------------------------------------------------------


class DetectCandidateHeaderBindingsTests(unittest.TestCase):

    def _steps(self, step_defs: list[dict]) -> list[dict]:
        """Build workflow step dicts from minimal defs."""
        return [
            {
                "case_id": d["case_id"],
                "workflow_step_index": i,
            }
            for i, d in enumerate(step_defs)
        ]

    def _cases(self, step_defs: list[dict]) -> dict:
        return {
            d["case_id"]: {
                "case_id": d["case_id"],
                "request_blueprint": d.get("blueprint", {}),
            }
            for d in step_defs
        }

    def _results(self, step_defs: list[dict]) -> dict:
        return {
            d["case_id"]: {
                "case_id": d["case_id"],
                "response_headers": d.get("response_headers", {}),
            }
            for d in step_defs
        }

    def test_none_step_results_returns_empty(self) -> None:
        step_defs = [
            {"case_id": "a"},
            {"case_id": "b", "blueprint": {"headers": {"cookie": "session={{session}}"}}},
        ]
        candidates = detect_candidate_header_bindings(
            self._steps(step_defs),
            self._cases(step_defs),
            step_results=None,
        )
        self.assertEqual(candidates, [])

    def test_no_set_cookie_in_response_returns_empty(self) -> None:
        step_defs = [
            {"case_id": "a", "response_headers": {"content-type": "application/json"}},
            {"case_id": "b", "blueprint": {"headers": {"cookie": "session={{session}}"}}},
        ]
        candidates = detect_candidate_header_bindings(
            self._steps(step_defs),
            self._cases(step_defs),
            step_results=self._results(step_defs),
        )
        self.assertEqual(candidates, [])

    def test_set_cookie_with_downstream_cookie_use_produces_exact_match(self) -> None:
        step_defs = [
            {
                "case_id": "step_a",
                "response_headers": {"set-cookie": "session=abc123; Path=/; HttpOnly"},
            },
            {
                "case_id": "step_b",
                "blueprint": {"headers": {"cookie": "session={{session}}"}},
            },
        ]
        candidates = detect_candidate_header_bindings(
            self._steps(step_defs),
            self._cases(step_defs),
            step_results=self._results(step_defs),
        )
        self.assertTrue(len(candidates) > 0)
        c = candidates[0]
        self.assertEqual(c["source_case_id"], "step_a")
        self.assertEqual(c["cookie_name"], "session")
        self.assertEqual(c["target_case_id"], "step_b")
        self.assertEqual(c["confidence_tier"], "exact_name_match")
        self.assertEqual(c["candidate_type"], "header_cookie_binding")
        self.assertEqual(c["source_header"], "set-cookie")
        self.assertEqual(c["target_header"], "cookie")

    def test_set_cookie_with_no_downstream_use_produces_unmatched(self) -> None:
        step_defs = [
            {
                "case_id": "step_a",
                "response_headers": {"set-cookie": "session=abc; Path=/"},
            },
            {
                "case_id": "step_b",
                "blueprint": {"headers": {"content-type": "application/json"}},
            },
        ]
        candidates = detect_candidate_header_bindings(
            self._steps(step_defs),
            self._cases(step_defs),
            step_results=self._results(step_defs),
        )
        self.assertTrue(len(candidates) > 0)
        c = candidates[0]
        self.assertIsNone(c["target_case_id"])
        self.assertEqual(c["confidence_tier"], "unmatched")

    def test_multiple_set_cookies_produce_multiple_candidates(self) -> None:
        step_defs = [
            {
                "case_id": "step_a",
                "response_headers": {
                    "set-cookie": ["session=abc; Path=/", "csrf=xyz; HttpOnly"],
                },
            },
            {
                "case_id": "step_b",
                "blueprint": {
                    "headers": {"cookie": "session=abc; csrf=xyz"},
                },
            },
        ]
        candidates = detect_candidate_header_bindings(
            self._steps(step_defs),
            self._cases(step_defs),
            step_results=self._results(step_defs),
        )
        cookie_names = {c["cookie_name"] for c in candidates}
        self.assertIn("session", cookie_names)
        self.assertIn("csrf", cookie_names)

    def test_downstream_step_with_cookie_header_name_in_header_names(self) -> None:
        """Step uses 'cookie' in header_names (not headers dict) — still detected."""
        step_defs = [
            {
                "case_id": "step_a",
                "response_headers": {"set-cookie": "token=abc; Path=/"},
            },
            {
                "case_id": "step_b",
                "blueprint": {"header_names": ["cookie", "content-type"]},
            },
        ]
        candidates = detect_candidate_header_bindings(
            self._steps(step_defs),
            self._cases(step_defs),
            step_results=self._results(step_defs),
        )
        matched = [c for c in candidates if c["confidence_tier"] == "exact_name_match"]
        self.assertTrue(len(matched) > 0)

    def test_candidate_has_required_fields(self) -> None:
        step_defs = [
            {"case_id": "a", "response_headers": {"set-cookie": "sess=1; Path=/"}},
            {"case_id": "b", "blueprint": {"headers": {"cookie": "sess=1"}}},
        ]
        candidates = detect_candidate_header_bindings(
            self._steps(step_defs),
            self._cases(step_defs),
            step_results=self._results(step_defs),
        )
        self.assertTrue(len(candidates) > 0)
        required = {
            "source_case_id", "source_header", "cookie_name", "target_case_id",
            "target_header", "confidence_tier", "reason", "candidate_type",
        }
        for c in candidates:
            for field in required:
                self.assertIn(field, c, f"Missing field '{field}' in candidate {c}")


# ---------------------------------------------------------------------------
# B2: session_continuity_note
# ---------------------------------------------------------------------------


class SessionContinuityNoteTests(unittest.TestCase):

    def test_none_when_no_candidates(self) -> None:
        self.assertIsNone(session_continuity_note([]))

    def test_note_for_matched_candidate(self) -> None:
        candidates = [
            {
                "source_case_id": "step_a",
                "cookie_name": "session",
                "target_case_id": "step_b",
                "confidence_tier": "exact_name_match",
            }
        ]
        note = session_continuity_note(candidates)
        self.assertIsNotNone(note)
        assert note is not None
        self.assertIn("step_a", note)
        self.assertIn("session", note)
        self.assertIn("step_b", note)

    def test_note_for_unmatched_candidate(self) -> None:
        candidates = [
            {
                "source_case_id": "step_a",
                "cookie_name": "csrf",
                "target_case_id": None,
                "confidence_tier": "unmatched",
            }
        ]
        note = session_continuity_note(candidates)
        self.assertIsNotNone(note)
        assert note is not None
        self.assertIn("step_a", note)
        self.assertIn("csrf", note)
        self.assertIn("operator review", note)

    def test_note_joins_multiple_candidates_with_pipe(self) -> None:
        candidates = [
            {
                "source_case_id": "step_a",
                "cookie_name": "session",
                "target_case_id": "step_b",
                "confidence_tier": "exact_name_match",
            },
            {
                "source_case_id": "step_a",
                "cookie_name": "csrf",
                "target_case_id": None,
                "confidence_tier": "unmatched",
            },
        ]
        note = session_continuity_note(candidates)
        assert note is not None
        self.assertIn(" | ", note)


# ---------------------------------------------------------------------------
# Manifest Integration Tests
# ---------------------------------------------------------------------------


class ManifestSessionContinuityIntegrationTests(unittest.TestCase):

    def _attack_plan_with_cookie(self, base_url: str = "https://example.com") -> dict:
        return {
            "plan_id": "test-plan",
            "cases": [
                {
                    "case_id": "step_a",
                    "method": "GET",
                    "path": "/api/auth/login",
                    "workflow_group": "auth_flow",
                    "workflow_step_index": 0,
                    "execution_mode": "live_safe_read",
                    "approval_mode": "auto",
                    "allowed": True,
                    "request_blueprint": {
                        "url": f"{base_url}/api/auth/login",
                        "host": "example.com",
                    },
                },
                {
                    "case_id": "step_b",
                    "method": "GET",
                    "path": "/api/profile",
                    "workflow_group": "auth_flow",
                    "workflow_step_index": 1,
                    "execution_mode": "live_safe_read",
                    "approval_mode": "auto",
                    "allowed": True,
                    "request_blueprint": {
                        "url": f"{base_url}/api/profile",
                        "host": "example.com",
                        "headers": {"cookie": "session={{session}}"},
                    },
                },
            ],
        }

    def test_manifest_has_candidate_header_binding_pairs_key(self) -> None:
        attack_plan = self._attack_plan_with_cookie()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        workflow = manifest["workflows"][0]
        self.assertIn("candidate_header_binding_pairs", workflow)

    def test_manifest_has_session_continuity_note_key(self) -> None:
        attack_plan = self._attack_plan_with_cookie()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        workflow = manifest["workflows"][0]
        self.assertIn("session_continuity_note", workflow)

    def test_session_continuity_note_is_none_at_plan_time(self) -> None:
        """At plan time (no live data), no cookies are detected, note must be None."""
        attack_plan = self._attack_plan_with_cookie()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        workflow = manifest["workflows"][0]
        self.assertIsNone(workflow["session_continuity_note"])

    def test_enrich_detects_set_cookie_and_populates_header_candidates(self) -> None:
        attack_plan = self._attack_plan_with_cookie()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)

        live_summary = {
            "results": [
                {
                    "workflow_id": "auth_flow",
                    "results": [
                        {
                            "case_id": "step_a",
                            "response_json": {"ok": True},
                            "response_headers": {"set-cookie": "session=real-session-token; Path=/; HttpOnly"},
                        }
                    ],
                }
            ]
        }
        cases = {c["case_id"]: c for c in attack_plan["cases"]}
        enriched = enrich_manifest_candidates(manifest, live_summary, cases=cases)
        workflow = enriched["workflows"][0]
        header_candidates = workflow["candidate_header_binding_pairs"]
        self.assertTrue(len(header_candidates) > 0)
        c = header_candidates[0]
        self.assertEqual(c["cookie_name"], "session")
        self.assertEqual(c["source_case_id"], "step_a")
        self.assertEqual(c["target_case_id"], "step_b")
        self.assertEqual(c["confidence_tier"], "exact_name_match")

    def test_enrich_sets_session_continuity_note_when_cookie_detected(self) -> None:
        attack_plan = self._attack_plan_with_cookie()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)

        live_summary = {
            "results": [
                {
                    "workflow_id": "auth_flow",
                    "results": [
                        {
                            "case_id": "step_a",
                            "response_headers": {"set-cookie": "session=abc; Path=/"},
                        }
                    ],
                }
            ]
        }
        cases = {c["case_id"]: c for c in attack_plan["cases"]}
        enriched = enrich_manifest_candidates(manifest, live_summary, cases=cases)
        note = enriched["workflows"][0]["session_continuity_note"]
        self.assertIsNotNone(note)
        assert note is not None
        self.assertIn("session", note)
        self.assertIn("step_a", note)

    def test_enrich_does_not_mutate_original_manifest(self) -> None:
        attack_plan = self._attack_plan_with_cookie()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        original_note = manifest["workflows"][0]["session_continuity_note"]

        live_summary = {
            "results": [
                {
                    "workflow_id": "auth_flow",
                    "results": [
                        {
                            "case_id": "step_a",
                            "response_headers": {"set-cookie": "session=x; Path=/"},
                        }
                    ],
                }
            ]
        }
        cases = {c["case_id"]: c for c in attack_plan["cases"]}
        enrich_manifest_candidates(manifest, live_summary, cases=cases)
        # Original manifest is unchanged
        self.assertEqual(manifest["workflows"][0]["session_continuity_note"], original_note)

    def test_header_candidates_not_in_response_bindings(self) -> None:
        """Header candidates must NEVER appear in response_bindings of any step."""
        attack_plan = self._attack_plan_with_cookie()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        live_summary = {
            "results": [
                {
                    "workflow_id": "auth_flow",
                    "results": [
                        {
                            "case_id": "step_a",
                            "response_headers": {"set-cookie": "session=x; Path=/"},
                        }
                    ],
                }
            ]
        }
        cases = {c["case_id"]: c for c in attack_plan["cases"]}
        enriched = enrich_manifest_candidates(manifest, live_summary, cases=cases)
        for workflow in enriched["workflows"]:
            for step in workflow["steps"]:
                for binding in step.get("response_bindings", []):
                    self.assertNotEqual(
                        binding.get("candidate_type"),
                        "header_cookie_binding",
                        "Header cookie candidate leaked into response_bindings",
                    )

    def test_candidate_binding_summary_includes_header_candidates_after_enrich(self) -> None:
        attack_plan = self._attack_plan_with_cookie()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        live_summary = {
            "results": [
                {
                    "workflow_id": "auth_flow",
                    "results": [
                        {
                            "case_id": "step_a",
                            "response_json": {"user": "alice"},
                            "response_headers": {"set-cookie": "session=x; Path=/"},
                        }
                    ],
                }
            ]
        }
        cases = {c["case_id"]: c for c in attack_plan["cases"]}
        enriched = enrich_manifest_candidates(manifest, live_summary, cases=cases)
        summary = enriched["candidate_binding_summary"]
        self.assertGreater(summary["total_candidate_count"], 0)
        # exact_name_match tier should appear (from header binding)
        self.assertIn("exact_name_match", summary["by_tier"])


if __name__ == "__main__":
    unittest.main()

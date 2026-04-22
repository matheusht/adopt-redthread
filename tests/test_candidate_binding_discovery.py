"""Tests for Phase A: Candidate Dependency Discovery.

Covers:
  A1 — discover_candidate_bindings (response-to-request field matching)
  A2 — alias_lookup (alias table bootstrap)
  A3 — discover_candidate_path_bindings (path slot matching)
  Manifest integration — candidates appear in manifest, not in response_bindings
"""

from __future__ import annotations

import unittest

from adapters.bridge.binding_alias_table import alias_lookup, all_entries, AliasEntry
from adapters.bridge.workflow_binding_inference import (
    discover_candidate_bindings,
    discover_candidate_path_bindings,
    _flatten_json_paths,
)
from adapters.bridge.workflow_review_manifest import (
    build_workflow_review_manifest,
    enrich_manifest_candidates,
    _candidate_summary,
)
from adapters.bridge.live_workflow import build_live_workflow_plan


# ---------------------------------------------------------------------------
# A2 — Alias Table Tests
# ---------------------------------------------------------------------------


class AliasTableTests(unittest.TestCase):

    def test_exact_name_match_is_first_result(self) -> None:
        results = alias_lookup("chat.id")
        tiers = [t for _, t in results]
        self.assertIn("exact_name_match", tiers)
        self.assertEqual(tiers[0], "exact_name_match")

    def test_chat_id_has_alias_to_chatId(self) -> None:
        targets = {t for t, _ in alias_lookup("chat.id")}
        self.assertIn("chatId", targets)

    def test_chat_id_has_alias_to_bare_id(self) -> None:
        targets = {t for t, _ in alias_lookup("chat.id")}
        self.assertIn("id", targets)

    def test_resource_id_has_alias_to_resourceId(self) -> None:
        targets = {t for t, _ in alias_lookup("resource.id")}
        self.assertIn("resourceId", targets)

    def test_thread_id_has_alias_to_threadId(self) -> None:
        targets = {t for t, _ in alias_lookup("thread.id")}
        self.assertIn("threadId", targets)

    def test_session_id_has_alias_to_sessionId(self) -> None:
        targets = {t for t, _ in alias_lookup("session.id")}
        self.assertIn("sessionId", targets)

    def test_heuristic_parent_id_camelcase(self) -> None:
        # "report.id" is not in the curated table, so heuristic should fire
        results = alias_lookup("report.id")
        tiers_by_target = {t: tier for t, tier in results}
        # Heuristic should produce "reportId"
        self.assertIn("reportId", tiers_by_target)
        self.assertEqual(tiers_by_target["reportId"], "heuristic_match")

    def test_order_id_in_alias_table_returns_alias_match(self) -> None:
        # order.id IS in the alias table, so it should produce alias_match for orderId
        results = alias_lookup("order.id")
        tiers_by_target = {t: tier for t, tier in results}
        self.assertIn("orderId", tiers_by_target)
        self.assertEqual(tiers_by_target["orderId"], "alias_match")

    def test_no_heuristic_for_non_id_key(self) -> None:
        results = alias_lookup("chat.title")
        tiers = [tier for _, tier in results]
        self.assertNotIn("heuristic_match", tiers)

    def test_all_entries_returns_list_of_alias_entries(self) -> None:
        entries = all_entries()
        self.assertTrue(len(entries) > 0)
        self.assertIsInstance(entries[0], AliasEntry)

    def test_no_duplicate_targets_in_results(self) -> None:
        for key in ["chat.id", "resource.id", "session.id", "thread.id"]:
            results = alias_lookup(key)
            targets = [t for t, _ in results]
            self.assertEqual(len(targets), len(set(targets)), f"Duplicate targets for {key}: {targets}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class FlattenJsonPathsTests(unittest.TestCase):

    def test_flat_dict(self) -> None:
        paths = _flatten_json_paths({"id": "abc", "name": "test"})
        keys = {k for k, _ in paths}
        self.assertIn("id", keys)
        self.assertIn("name", keys)

    def test_nested_dict(self) -> None:
        paths = _flatten_json_paths({"chat": {"id": "abc", "title": "T"}})
        keys = {k for k, _ in paths}
        self.assertIn("chat.id", keys)
        self.assertIn("chat.title", keys)

    def test_lists_are_skipped(self) -> None:
        paths = _flatten_json_paths({"items": [1, 2, 3], "id": "x"})
        keys = {k for k, _ in paths}
        self.assertNotIn("items", keys)
        self.assertIn("id", keys)

    def test_non_dict_input_returns_empty(self) -> None:
        self.assertEqual(_flatten_json_paths(None), [])  # type: ignore[arg-type]
        self.assertEqual(_flatten_json_paths("string"), [])  # type: ignore[arg-type]
        self.assertEqual(_flatten_json_paths([1, 2]), [])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A1 — discover_candidate_bindings tests
# ---------------------------------------------------------------------------


class CandidateBindingDiscoveryA1Tests(unittest.TestCase):

    def _step_n1(self, body_json: dict) -> dict:
        return {
            "case_id": "step_b",
            "request_blueprint": {
                "url": "https://example.com/api/chat",
                "body_json": body_json,
            },
        }

    def test_exact_name_match_detected(self) -> None:
        response_json = {"id": "abc-123"}
        step_n1 = self._step_n1({"id": "placeholder", "message": "hi"})
        candidates = discover_candidate_bindings(response_json, step_n1, "step_a", "step_b")
        tiers = {c["confidence_tier"] for c in candidates}
        targets = {c["target_path"] for c in candidates}
        self.assertIn("exact_name_match", tiers)
        self.assertIn("id", targets)

    def test_alias_match_chat_id_to_chatId(self) -> None:
        response_json = {"chat": {"id": "chat-xyz"}}
        step_n1 = self._step_n1({"chatId": "placeholder"})
        candidates = discover_candidate_bindings(response_json, step_n1, "step_a", "step_b")
        alias_candidates = [c for c in candidates if c["confidence_tier"] == "alias_match"]
        targets = {c["target_path"] for c in alias_candidates}
        self.assertIn("chatId", targets)

    def test_alias_match_chat_id_to_bare_id(self) -> None:
        response_json = {"chat": {"id": "chat-xyz"}}
        step_n1 = self._step_n1({"id": "placeholder", "chatId": "placeholder"})
        candidates = discover_candidate_bindings(response_json, step_n1, "step_a", "step_b")
        targets = {c["target_path"] for c in candidates}
        self.assertIn("id", targets)
        self.assertIn("chatId", targets)

    def test_heuristic_match_report_id(self) -> None:
        # report.id is NOT in the curated alias table, so heuristic fires
        response_json = {"report": {"id": "rpt-999"}}
        step_n1 = self._step_n1({"reportId": "placeholder"})
        candidates = discover_candidate_bindings(response_json, step_n1, "step_a", "step_b")
        heuristic_candidates = [c for c in candidates if c["confidence_tier"] == "heuristic_match"]
        targets = {c["target_path"] for c in heuristic_candidates}
        self.assertIn("reportId", targets)

    def test_non_id_fields_do_not_generate_heuristic_candidates(self) -> None:
        response_json = {"chat": {"title": "My Chat", "status": "active"}}
        step_n1 = self._step_n1({"title": "placeholder"})
        candidates = discover_candidate_bindings(response_json, step_n1, "step_a", "step_b")
        heuristic_candidates = [c for c in candidates if c["confidence_tier"] == "heuristic_match"]
        self.assertEqual(len(heuristic_candidates), 0)

    def test_none_response_json_returns_empty(self) -> None:
        step_n1 = self._step_n1({"chatId": "placeholder"})
        candidates = discover_candidate_bindings(None, step_n1, "step_a", "step_b")
        self.assertEqual(candidates, [])

    def test_candidate_has_required_fields(self) -> None:
        response_json = {"chat": {"id": "abc"}}
        step_n1 = self._step_n1({"chatId": "x"})
        candidates = discover_candidate_bindings(response_json, step_n1, "step_a", "step_b")
        self.assertTrue(len(candidates) > 0)
        for c in candidates:
            self.assertIn("source_case_id", c)
            self.assertIn("source_key", c)
            self.assertIn("target_case_id", c)
            self.assertIn("target_field", c)
            self.assertIn("target_path", c)
            self.assertIn("confidence_tier", c)
            self.assertIn("reason", c)
            self.assertIn("candidate_type", c)

    def test_no_duplicates_in_candidates(self) -> None:
        response_json = {"chat": {"id": "abc"}}
        step_n1 = self._step_n1({"chatId": "x", "id": "y"})
        candidates = discover_candidate_bindings(response_json, step_n1, "step_a", "step_b")
        dedup_keys = [(c["source_key"], c["target_field"], c["target_path"]) for c in candidates]
        self.assertEqual(len(dedup_keys), len(set(dedup_keys)))


# ---------------------------------------------------------------------------
# A3 — discover_candidate_path_bindings tests
# ---------------------------------------------------------------------------


class CandidatePathBindingDiscoveryA3Tests(unittest.TestCase):

    def test_slot_matched_by_exact_name(self) -> None:
        response_json = {"id": "abc-123"}
        url = "https://example.com/api/chats/{id}/messages"
        candidates = discover_candidate_path_bindings(response_json, url, "step_a", "step_b")
        matched = [c for c in candidates if c["confidence_tier"] != "unmatched"]
        self.assertTrue(len(matched) > 0)
        self.assertEqual(matched[0]["slot"], "id")

    def test_slot_matched_by_alias(self) -> None:
        response_json = {"chat": {"id": "chat-xyz"}}
        url = "https://example.com/api/chats/{chatId}/messages"
        candidates = discover_candidate_path_bindings(response_json, url, "step_a", "step_b")
        matched = [c for c in candidates if c["confidence_tier"] == "alias_match"]
        self.assertTrue(len(matched) > 0)
        self.assertEqual(matched[0]["slot"], "chatId")
        self.assertEqual(matched[0]["source_key"], "chat.id")

    def test_unmatched_slot_appears_with_unmatched_tier(self) -> None:
        response_json = {"status": "ok"}
        url = "https://example.com/api/chats/{chatId}"
        candidates = discover_candidate_path_bindings(response_json, url, "step_a", "step_b")
        unmatched = [c for c in candidates if c["confidence_tier"] == "unmatched"]
        self.assertTrue(len(unmatched) > 0)
        self.assertEqual(unmatched[0]["slot"], "chatId")

    def test_no_slots_returns_empty(self) -> None:
        response_json = {"id": "abc"}
        url = "https://example.com/api/chats/static"
        candidates = discover_candidate_path_bindings(response_json, url, "step_a", "step_b")
        self.assertEqual(candidates, [])

    def test_none_response_with_slots_returns_all_unmatched(self) -> None:
        url = "https://example.com/api/chats/{chatId}/{id}"
        candidates = discover_candidate_path_bindings(None, url, "step_a", "step_b")
        self.assertTrue(len(candidates) > 0)
        for c in candidates:
            self.assertEqual(c["confidence_tier"], "unmatched")

    def test_candidate_has_required_fields(self) -> None:
        response_json = {"chat": {"id": "abc"}}
        url = "https://example.com/api/chats/{chatId}"
        candidates = discover_candidate_path_bindings(response_json, url, "step_a", "step_b")
        self.assertTrue(len(candidates) > 0)
        for c in candidates:
            self.assertIn("source_case_id", c)
            self.assertIn("target_case_id", c)
            self.assertIn("target_field", c)
            self.assertIn("slot", c)
            self.assertIn("placeholder", c)
            self.assertIn("confidence_tier", c)
            self.assertIn("reason", c)

    def test_placeholder_format_uses_curly_braces(self) -> None:
        response_json = {"id": "x"}
        url = "https://example.com/api/{id}"
        candidates = discover_candidate_path_bindings(response_json, url, "step_a", "step_b")
        self.assertTrue(len(candidates) > 0)
        self.assertEqual(candidates[0]["placeholder"], "{id}")


# ---------------------------------------------------------------------------
# Candidate summary
# ---------------------------------------------------------------------------


class CandidateSummaryTests(unittest.TestCase):

    def test_empty_list(self) -> None:
        summary = _candidate_summary([])
        self.assertEqual(summary["total_candidate_count"], 0)
        self.assertEqual(summary["by_tier"], {})

    def test_counts_by_tier(self) -> None:
        candidates = [
            {"confidence_tier": "exact_name_match"},
            {"confidence_tier": "alias_match"},
            {"confidence_tier": "alias_match"},
            {"confidence_tier": "heuristic_match"},
        ]
        summary = _candidate_summary(candidates)
        self.assertEqual(summary["total_candidate_count"], 4)
        self.assertEqual(summary["by_tier"]["exact_name_match"], 1)
        self.assertEqual(summary["by_tier"]["alias_match"], 2)
        self.assertEqual(summary["by_tier"]["heuristic_match"], 1)


# ---------------------------------------------------------------------------
# Manifest Integration Tests
# ---------------------------------------------------------------------------


class ManifestCandidateIntegrationTests(unittest.TestCase):

    def _minimal_attack_plan(self, base_url: str = "https://example.com") -> dict:
        return {
            "plan_id": "test-plan",
            "cases": [
                {
                    "case_id": "step_a",
                    "method": "GET",
                    "path": "/api/chats",
                    "workflow_group": "chat_flow",
                    "workflow_step_index": 0,
                    "execution_mode": "live_safe_read",
                    "approval_mode": "auto",
                    "allowed": True,
                    "request_blueprint": {"url": f"{base_url}/api/chats", "host": "example.com"},
                },
                {
                    "case_id": "step_b",
                    "method": "POST",
                    "path": "/api/chat",
                    "workflow_group": "chat_flow",
                    "workflow_step_index": 1,
                    "execution_mode": "live_reviewed_write_staging",
                    "approval_mode": "human_review",
                    "allowed": False,
                    "target_env": "staging",
                    "request_blueprint": {
                        "url": f"{base_url}/api/chat",
                        "host": "example.com",
                        "body_json": {"chatId": "placeholder", "id": "placeholder"},
                    },
                },
            ],
        }

    def test_manifest_has_candidate_binding_summary(self) -> None:
        attack_plan = self._minimal_attack_plan()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        self.assertIn("candidate_binding_summary", manifest)
        self.assertIn("total_candidate_count", manifest["candidate_binding_summary"])
        self.assertIn("by_tier", manifest["candidate_binding_summary"])

    def test_manifest_workflow_has_candidate_binding_pairs(self) -> None:
        attack_plan = self._minimal_attack_plan()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        workflow_manifest = manifest["workflows"][0]
        self.assertIn("candidate_binding_pairs", workflow_manifest)

    def test_candidate_bindings_not_in_response_bindings(self) -> None:
        """Candidates must NEVER appear in response_bindings of any step."""
        attack_plan = self._minimal_attack_plan()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        for workflow in manifest["workflows"]:
            for step in workflow["steps"]:
                for binding in step.get("response_bindings", []):
                    self.assertNotEqual(
                        binding.get("candidate_type"),
                        "response_to_request_body",
                        "Candidate binding leaked into response_bindings",
                    )

    def test_enrich_manifest_with_live_response_json(self) -> None:
        attack_plan = self._minimal_attack_plan()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)

        # Simulate a live replay summary with response JSON for step_a
        live_summary = {
            "results": [
                {
                    "workflow_id": "chat_flow",
                    "results": [
                        {
                            "case_id": "step_a",
                            "response_json": {"chat": {"id": "real-chat-id"}, "sessionId": "sess-abc"},
                        }
                    ],
                }
            ]
        }

        enriched = enrich_manifest_candidates(manifest, live_summary)
        workflow = enriched["workflows"][0]
        pairs = workflow["candidate_binding_pairs"]
        self.assertTrue(len(pairs) > 0)
        pair = pairs[0]

        # A1 candidates should now be populated (real response JSON available)
        self.assertTrue(len(pair["candidate_bindings"]) > 0)

        # Check that chatId alias candidate appears
        targets = {c["target_path"] for c in pair["candidate_bindings"]}
        self.assertIn("chatId", targets)

    def test_enrich_does_not_mutate_original_manifest(self) -> None:
        attack_plan = self._minimal_attack_plan()
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        original_pairs = list(manifest["workflows"][0]["candidate_binding_pairs"])

        live_summary = {
            "results": [
                {
                    "workflow_id": "chat_flow",
                    "results": [{"case_id": "step_a", "response_json": {"chat": {"id": "x"}}}],
                }
            ]
        }
        enrich_manifest_candidates(manifest, live_summary)
        # Original manifest is unchanged
        self.assertEqual(manifest["workflows"][0]["candidate_binding_pairs"], original_pairs)

    def test_path_slot_candidates_appear_in_manifest_when_url_has_slots(self) -> None:
        attack_plan = {
            "plan_id": "test",
            "cases": [
                {
                    "case_id": "step_a",
                    "method": "GET",
                    "path": "/api/chats",
                    "workflow_group": "g",
                    "workflow_step_index": 0,
                    "execution_mode": "live_safe_read",
                    "approval_mode": "auto",
                    "allowed": True,
                    "request_blueprint": {"url": "https://x.com/api/chats", "host": "x.com"},
                },
                {
                    "case_id": "step_b",
                    "method": "GET",
                    "path": "/api/chats/{chatId}/messages",
                    "workflow_group": "g",
                    "workflow_step_index": 1,
                    "execution_mode": "live_safe_read",
                    "approval_mode": "auto",
                    "allowed": True,
                    "request_blueprint": {
                        "url": "https://x.com/api/chats/{chatId}/messages",
                        "host": "x.com",
                    },
                },
            ],
        }
        workflow_plan = build_live_workflow_plan(attack_plan)
        manifest = build_workflow_review_manifest(workflow_plan, None)
        pairs = manifest["workflows"][0]["candidate_binding_pairs"]
        self.assertTrue(len(pairs) > 0)
        path_candidates = pairs[0]["candidate_path_bindings"]
        # {chatId} slot must appear — unmatched at plan time (no live response JSON yet)
        slots = {c["slot"] for c in path_candidates}
        self.assertIn("chatId", slots)


if __name__ == "__main__":
    unittest.main()

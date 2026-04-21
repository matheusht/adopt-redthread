from __future__ import annotations

import unittest

from adapters.zapi.loader import build_fixture_bundle


class ZapiLoaderTests(unittest.TestCase):
    def test_zapi_fixture_bundle_has_expected_counts_and_metadata(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_discovery.json")

        self.assertEqual(bundle["source"], "zapi")
        self.assertEqual(bundle["ingestion_mode"], "catalog")
        self.assertEqual(bundle["fixture_count"], 4)

        fixtures = {item["name"]: item for item in bundle["fixtures"]}
        self.assertEqual(fixtures["get_api_customers"]["replay_class"], "safe_read_with_review")
        self.assertEqual(fixtures["get_api_reports_export"]["data_sensitivity"], "pii")
        self.assertEqual(fixtures["delete_api_admin_users_user_id"]["risk_level"], "high")
        self.assertTrue(fixtures["delete_api_admin_users_user_id"]["approval_required"])
        self.assertIn("privilege_escalation", fixtures["delete_api_admin_users_user_id"]["candidate_attack_types"])

    def test_har_fixture_bundle_extracts_real_app_endpoints_and_drops_noise(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_filtered_har.json")

        self.assertEqual(bundle["source"], "zapi")
        self.assertEqual(bundle["ingestion_mode"], "har")
        self.assertEqual(bundle["fixture_count"], 4)

        fixtures = {item["name"]: item for item in bundle["fixtures"]}
        self.assertNotIn("post_weaver_api_v1_event_report", fixtures)
        self.assertIn("post_weaver_api_v1_conversation_accept_msg", fixtures)
        self.assertIn("post_weaver_api_v1_ugc_memory_get_memory_detail", fixtures)

        conversation = fixtures["post_weaver_api_v1_conversation_accept_msg"]
        self.assertEqual(conversation["endpoint_family"], "conversation")
        self.assertEqual(conversation["replay_class"], "manual_review")
        self.assertIn("prompt_injection", conversation["candidate_attack_types"])
        self.assertIn("x-token", conversation["auth_hints"])

        memory = fixtures["post_weaver_api_v1_ugc_memory_get_memory_detail"]
        self.assertEqual(memory["data_sensitivity"], "pii")
        self.assertIn("authorization_bypass", memory["candidate_attack_types"])
        self.assertIn("data_exfiltration", memory["candidate_attack_types"])


if __name__ == "__main__":
    unittest.main()

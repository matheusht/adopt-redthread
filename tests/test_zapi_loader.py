from __future__ import annotations

import unittest

from adapters.zapi.loader import build_fixture_bundle


class ZapiLoaderTests(unittest.TestCase):
    def test_zapi_fixture_bundle_has_expected_counts_and_metadata(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_discovery.json")

        self.assertEqual(bundle["source"], "zapi")
        self.assertEqual(bundle["fixture_count"], 4)

        fixtures = {item["name"]: item for item in bundle["fixtures"]}
        self.assertEqual(fixtures["get_api_customers"]["replay_class"], "safe_read_with_review")
        self.assertEqual(fixtures["get_api_reports_export"]["data_sensitivity"], "pii")
        self.assertEqual(fixtures["delete_api_admin_users_user_id"]["risk_level"], "high")
        self.assertTrue(fixtures["delete_api_admin_users_user_id"]["approval_required"])
        self.assertIn("privilege_escalation", fixtures["delete_api_admin_users_user_id"]["candidate_attack_types"])


if __name__ == "__main__":
    unittest.main()

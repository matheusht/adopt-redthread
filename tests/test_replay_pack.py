from __future__ import annotations

import unittest

from adapters.zapi.loader import build_fixture_bundle
from scripts.generate_replay_pack import build_replay_pack


class ReplayPackTests(unittest.TestCase):
    def test_replay_pack_groups_fixtures_by_replay_class(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_discovery.json")
        replay_pack = build_replay_pack(bundle)

        self.assertEqual(replay_pack["summary"]["safe_read_count"], 2)
        self.assertEqual(replay_pack["summary"]["write_review_count"], 1)
        self.assertEqual(replay_pack["summary"]["sandbox_only_count"], 1)

        safe_names = {item["name"] for item in replay_pack["safe_read_probes"]}
        self.assertEqual(safe_names, {"get_api_customers", "get_api_reports_export"})

        write_item = replay_pack["write_path_review_items"][0]
        self.assertTrue(write_item["approval_required"])
        self.assertIn("parameter_grounding", write_item["review_focus"])


if __name__ == "__main__":
    unittest.main()

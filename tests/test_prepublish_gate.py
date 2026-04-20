from __future__ import annotations

import unittest

from adapters.zapi.loader import build_fixture_bundle
from scripts.generate_replay_pack import build_replay_pack
from scripts.prepublish_gate import build_gate_verdict


class PrepublishGateTests(unittest.TestCase):
    def test_prepublish_gate_blocks_when_sandbox_only_items_exist(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_discovery.json")
        replay_pack = build_replay_pack(bundle)

        verdict = build_gate_verdict(replay_pack, allow_sandbox_only=False)

        self.assertEqual(verdict["decision"], "block")
        self.assertIn("sandbox_only_items_present", verdict["blockers"])
        self.assertIn("manual_review_required_for_write_paths", verdict["warnings"])

    def test_prepublish_gate_can_downgrade_to_review_when_sandbox_items_are_allowed(self) -> None:
        bundle = build_fixture_bundle("fixtures/zapi_samples/sample_discovery.json")
        replay_pack = build_replay_pack(bundle)

        verdict = build_gate_verdict(replay_pack, allow_sandbox_only=True)

        self.assertEqual(verdict["decision"], "review")
        self.assertEqual(verdict["blockers"], [])
        self.assertIn("manual_review_required_for_write_paths", verdict["warnings"])


if __name__ == "__main__":
    unittest.main()

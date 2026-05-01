from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_redthread_evidence_contract_proposal import build_redthread_evidence_contract_proposal


class RedThreadEvidenceContractProposalTests(unittest.TestCase):
    def test_contract_proposal_is_generic_and_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal = build_redthread_evidence_contract_proposal(output_dir=root / "out", doc_path=root / "proposal.md")
            proposal_md = (root / "proposal.md").read_text(encoding="utf-8")

        self.assertEqual(proposal["schema_version"], "redthread.evidence_contract_proposal.v0")
        self.assertEqual(proposal["status"], "proposal_only_not_upstreamed")
        self.assertTrue(proposal["configured_marker_check"]["passed"])
        self.assertEqual(proposal["configured_marker_check"]["marker_hit_count"], 0)
        self.assertEqual(len(proposal["required_sections"]), 6)
        section_names = {section["name"] for section in proposal["required_sections"]}
        self.assertIn("promotion_recommendation", section_names)
        self.assertIn("next_evidence_guidance", section_names)
        workflow_fields = next(section["fields"] for section in proposal["required_sections"] if section["name"] == "workflow_evidence")
        attack_fields = next(section["fields"] for section in proposal["required_sections"] if section["name"] == "attack_context_summary")
        self.assertIn("ordered_operations", workflow_fields)
        self.assertIn("tool_action_schemas", attack_fields)
        self.assertIn("RedThread should own", proposal_md)
        self.assertIn("Adapters should own", proposal_md)
        self.assertIn("whole-application safety", proposal_md)
        self.assertNotIn("authorization:", proposal_md.casefold())
        self.assertNotIn("cookie:", proposal_md.casefold())

    def test_required_field_names_do_not_use_source_specific_ingestion_names(self) -> None:
        proposal = build_redthread_evidence_contract_proposal(output_dir=Path(tempfile.mkdtemp()) / "out", doc_path=None)
        forbidden = {"adopt", "zapi", "noui"}

        field_text = " ".join(
            field.casefold()
            for section in proposal["required_sections"]
            for field in section["fields"]
        )

        for word in forbidden:
            self.assertNotIn(word, field_text)


if __name__ == "__main__":
    unittest.main()

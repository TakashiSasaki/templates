import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "lifecycle.md"


class LedgerOverviewTests(unittest.TestCase):
    def test_lifecycle_page_explains_distinct_ledger_roles(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        for required in (
            "Requirement / evidence ledger",
            "Lifecycle checkpoint ledger",
            "Review-finding ledger",
            "Repository-change Work ledger",
            "current product state",
            "validated transition history",
            "repository-associated but should not normally be a",
            "operational projection",
            "not an agent transcript",
            "next safe action",
            "provider facts",
        ):
            self.assertIn(required, text)

    def test_lifecycle_page_preserves_authority_boundaries_and_existing_route(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("not a new semantic authority", text)
        self.assertIn("owned by the `composition` provider", text)
        self.assertIn("owned by Policy", text)
        self.assertIn("Staged Policy repository-change candidate", text)
        self.assertIn("staged architecture here, not current", text)
        self.assertIn("c5a3294809a1066bf59b83f467f1d597f885289a", text)
        self.assertIn("[Implementation evidence](implementation-evidence/)", text)
        self.assertIn("[Lifecycle checkpoints](checkpoints/)", text)
        self.assertIn("[Policy–Composition coexistence](../coexistence/)", text)

        manifest = (ROOT / "site-manifest.json").read_text(encoding="utf-8")
        self.assertIn('"document": "lifecycle-overview"', manifest)
        self.assertIn('"destination": "lifecycle/index.md"', manifest)


if __name__ == "__main__":
    unittest.main()

import json
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

    def test_reference_consumer_examples_match_current_site_state(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        evidence = json.loads(
            (ROOT / "contracts" / "implementation-evidence.json").read_text(encoding="utf-8")
        )
        self.assertEqual(evidence["mode"], "product")
        self.assertIn("current canonical Site base", text)
        self.assertIn("`contracts/implementation-evidence.json`\nis in `product` mode", text)

        ledger = json.loads(
            (ROOT / "contracts" / "lifecycle-checkpoints.json").read_text(encoding="utf-8")
        )
        checkpoints = ledger["checkpoints"]
        self.assertEqual(
            [item["id"] for item in checkpoints],
            [
                "site-reference-adoption",
                "site-reference-adoption-product",
                "routes-v5-publication",
                "routes-v5-publication-product",
            ],
        )
        self.assertEqual([item["sequence"] for item in checkpoints], [1, 2, 3, 4])
        self.assertEqual(
            [item["phase"] for item in checkpoints],
            ["planning", "product", "planning", "product"],
        )
        self.assertEqual(
            [item["changeKind"] for item in checkpoints],
            ["initial", "initial", "specification-change", "specification-change"],
        )
        self.assertEqual(
            [item["parentId"] for item in checkpoints],
            [
                None,
                "site-reference-adoption",
                "site-reference-adoption-product",
                "routes-v5-publication",
            ],
        )
        self.assertEqual(
            checkpoints[0]["snapshotPath"],
            "artifacts/lifecycle/001-site-reference-adoption",
        )
        self.assertEqual(
            checkpoints[0]["manifestSha256"],
            "9ec8d87ea01cf6f178422ca39589882ac3aac86dbc6084d7cc71f5a03df667d4",
        )
        self.assertEqual(
            checkpoints[-1]["snapshotPath"],
            "artifacts/lifecycle/004-routes-v5-publication-product",
        )
        self.assertEqual(
            checkpoints[-1]["manifestSha256"],
            "c3ba91ed78fc90f780213b443182b17c38316d77d92f0151fb3d00392e77d9f1",
        )
        for value in (
            checkpoints[0]["id"],
            checkpoints[0]["snapshotPath"],
            checkpoints[0]["manifestSha256"],
            checkpoints[-1]["id"],
            checkpoints[-1]["snapshotPath"],
            checkpoints[-1]["manifestSha256"],
        ):
            self.assertIn(value, text)

    def test_work_ledger_example_is_explicitly_staged_against_published_policy(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        sources = json.loads((ROOT / "publication-sources.json").read_text(encoding="utf-8"))
        self.assertEqual(
            sources["publications"]["composition"]["revision"],
            "806f8574a8b9607c5d6cf438f96e5801ea69f7ae",
        )
        policy_revision = sources["publications"]["policy"]["revision"]
        self.assertEqual(policy_revision, "c5a3294809a1066bf59b83f467f1d597f885289a")
        self.assertIn(policy_revision, text)
        self.assertIn("Policy PR stack `#754 -> #755`", text)
        self.assertIn("c2e23789ebabee4d1f35653e86ebe8f61ab6e8bf", text)
        self.assertIn("e73757b93bb7a97c2e6a618d899f652933c9c795", text)
        self.assertIn("**not** make the Work ledger", text)


if __name__ == "__main__":
    unittest.main()

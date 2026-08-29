from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = ROOT / "docs" / "glossary.yml"
CONCEPTS = ROOT / "docs" / "policy-concepts.md"
MKDOCS = ROOT / "mkdocs.yml"

TERMINOLOGY_IDS = {
    "templates-policy-adoption",
    "templates-policy-fresh-adoption",
    "templates-policy-migration-adoption",
    "templates-policy-render-operation",
    "templates-policy-validate-operation",
    "templates-policy-check-operation",
}


class PolicyTerminologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        glossary = yaml.safe_load(GLOSSARY.read_text(encoding="utf-8"))
        cls.terms = {term["id"]: term for term in glossary["terms"]}
        cls.concepts = CONCEPTS.read_text(encoding="utf-8")

    def test_policy_operation_terms_are_canonical_and_localized(self) -> None:
        self.assertTrue(TERMINOLOGY_IDS <= self.terms.keys())
        for term_id in TERMINOLOGY_IDS:
            with self.subTest(term_id=term_id):
                term = self.terms[term_id]
                self.assertEqual(term.get("origin"), "repository")
                self.assertTrue(term.get("definition", "").strip())
                self.assertTrue(
                    term.get("localized_labels", {})
                    .get("ja", {})
                    .get("term", "")
                    .strip()
                )

    def test_adoption_strategies_are_state_derived_and_distinct(self) -> None:
        adoption = self.terms["templates-policy-adoption"]
        self.assertIn("first-time onboarding", adoption["definition"])
        self.assertIn("Installing the agent-policy skill", adoption["definition"])
        self.assertIn("templates-policy-fresh-adoption", adoption["related_terms"])
        self.assertIn("templates-policy-migration-adoption", adoption["related_terms"])

        fresh = self.terms["templates-policy-fresh-adoption"]["definition"]
        self.assertIn("unmanaged-empty", fresh)
        self.assertIn("hidden init primitive", fresh)
        self.assertIn("without a staged adoption-state transaction", fresh)

        migration = self.terms["templates-policy-migration-adoption"]["definition"]
        self.assertIn("unmanaged-existing", migration)
        self.assertIn("preview", migration)
        self.assertIn("finalize --apply", migration)

    def test_render_validate_and_check_have_different_contracts(self) -> None:
        render = self.terms["templates-policy-render-operation"]["definition"]
        validate = self.terms["templates-policy-validate-operation"]["definition"]
        check = self.terms["templates-policy-check-operation"]["definition"]

        self.assertIn("mutating", render)
        self.assertIn("regenerates", render)
        self.assertIn("read-only", validate)
        self.assertIn("does not assert", validate)
        self.assertIn("read-only", check)
        self.assertIn("does not regenerate", check)

    def test_managed_repository_does_not_imply_validation(self) -> None:
        managed = self.terms["templates-policy-managed-repository"]["definition"]
        self.assertIn("does not assert", managed)
        self.assertIn("validations", managed)
        self.assertIn("inconsistent", managed)

    def test_first_reader_guide_preserves_disambiguation_boundaries(self) -> None:
        for heading in (
            "## Adoption is the user-facing onboarding operation",
            "## Fresh adoption and migration adoption are not interchangeable",
            "## Managed does not mean validated",
            "## Render, validate, and check have different contracts",
            "## Prepared and finalized are migration-adoption states",
            "## Stable release is not the policy branch tip",
            "## Words that should usually be qualified",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, self.concepts)

    def test_policy_concepts_are_in_provider_documentation_navigation(self) -> None:
        mkdocs = MKDOCS.read_text(encoding="utf-8")
        self.assertIn("Policy concepts: policy-concepts.md", mkdocs)


if __name__ == "__main__":
    unittest.main()

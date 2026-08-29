from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = ROOT / "docs" / "glossary.yml"

SURVIVING_HISTORICAL_IDS = {
    "templates-webapp-template-mode",
    "templates-webapp-product-mode",
    "templates-webapp-contract-family",
    "templates-webapp-candidate-revision",
}

CURRENT_COMPOSITION_IDS = {
    "templates-composition-planning-mode",
    "templates-composition-consumer-repository",
    "templates-composition-initial-operation",
    "templates-composition-update-operation",
    "templates-composition-upgrade-operation",
    "templates-composition-component-version",
    "templates-composition-release-readiness",
    "templates-composition-lifecycle-checkpoint",
}

RETIRED_REVISION_ROLE_IDS = {
    "templates-webapp-merge-test-revision",
    "templates-webapp-released-revision",
    "templates-webapp-deployed-revision",
}


class GlossaryTerminologyContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
        cls.terms = {term["id"]: term for term in cls.glossary["terms"]}

    def test_surviving_historical_concepts_keep_stable_ids(self) -> None:
        self.assertTrue(SURVIVING_HISTORICAL_IDS <= self.terms.keys())
        for term_id in SURVIVING_HISTORICAL_IDS:
            with self.subTest(term_id=term_id):
                usage = self.terms[term_id].get("repository_usage", "")
                self.assertTrue(usage)
                self.assertIn("retained", usage)
                self.assertTrue(
                    "Composition authority migration" in usage
                    or "former Webapp authority" in usage,
                    usage,
                )

    def test_current_composition_lifecycle_terms_are_canonical(self) -> None:
        self.assertTrue(CURRENT_COMPOSITION_IDS <= self.terms.keys())

        product_usage = self.terms["templates-webapp-product-mode"]["repository_usage"]
        for overclaim in ("implementation complete", "release ready", "released", "deployed"):
            with self.subTest(overclaim=overclaim):
                self.assertIn(overclaim, product_usage)

        planning_usage = self.terms["templates-composition-planning-mode"]["repository_usage"]
        self.assertIn("contract state", planning_usage)
        self.assertIn("not a synonym", planning_usage)

        update_usage = self.terms["templates-composition-update-operation"]["repository_usage"]
        self.assertIn("does not accept replacement configuration", update_usage)
        self.assertIn("cannot cross", update_usage)

        upgrade_usage = self.terms["templates-composition-upgrade-operation"]["repository_usage"]
        self.assertIn("explicit replacement intent", upgrade_usage)
        self.assertIn("compatibility-boundary", upgrade_usage)

        version_usage = self.terms["templates-composition-component-version"]["repository_usage"]
        self.assertIn("not Semantic Versioning", version_usage)

        readiness_usage = self.terms["templates-composition-release-readiness"]["repository_usage"]
        for non_claim in ("packaging", "signing", "deployment", "external artifact identity"):
            with self.subTest(non_claim=non_claim):
                self.assertIn(non_claim, readiness_usage)

    def test_consumer_repository_is_not_application_end_user(self) -> None:
        usage = self.terms["templates-composition-consumer-repository"]["repository_usage"]
        self.assertIn("not to an application end user or customer", usage)

    def test_lifecycle_checkpoint_does_not_overclaim_chronology(self) -> None:
        usage = self.terms["templates-composition-lifecycle-checkpoint"]["repository_usage"]
        self.assertIn("not a trusted timestamp", usage)
        self.assertIn("external attestation", usage)

    def test_retired_revision_roles_are_not_reintroduced(self) -> None:
        self.assertFalse(RETIRED_REVISION_ROLE_IDS & self.terms.keys())

    def test_composition_local_related_terms_resolve(self) -> None:
        ids = set(self.terms)
        cross_provider = {"templates-artifact-contract", "templates-policy-profile"}
        for term in self.glossary["terms"]:
            for related in term.get("related_terms", []):
                if related.startswith("external-") or related in cross_provider:
                    continue
                with self.subTest(term=term["id"], related=related):
                    self.assertIn(related, ids)


if __name__ == "__main__":
    unittest.main()

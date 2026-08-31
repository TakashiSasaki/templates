from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class WebsiteReaderConsistencyTests(unittest.TestCase):
    def test_root_reader_entrypoint_exposes_all_current_artifact_choices(self) -> None:
        readme = text("README.md")
        for expected in (
            "Choose Website or Web application",
            "Website product walkthrough",
            "artifact.website-core",
            "artifact.webapp-core",
            "foundation.web",
            "four reusable component roles",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, readme)
        self.assertNotIn("A minimal static/CDN Web application", readme)

    def test_root_reader_assigns_web_evidence_to_actual_component_owners(self) -> None:
        readme = text("README.md")
        japanese = text("translations/ja/README.md")
        for surface in (readme, japanese):
            with self.subTest(surface="ja" if surface is japanese else "en"):
                self.assertIn("foundation.web", surface)
                self.assertIn("browser identity", surface)
                self.assertIn("generalized routes", surface)
                self.assertIn("viewports", surface)
                self.assertIn("artifact.website-core", surface)
                self.assertIn("artifact.webapp-core", surface)
                self.assertIn("lifecycle.implementation-evidence", surface)
                self.assertNotIn("shared Web evidence infrastructure", surface)
        self.assertIn("evidence-target derivation and validator logic", readme)
        self.assertIn("artifact-neutral evidence machinery", readme)
        self.assertIn("evidence-target derivation / validator logic", japanese)
        self.assertIn("artifact-neutral evidence machinery", japanese)

    def test_consumer_guide_routes_browser_artifact_selection_through_decision_guide(self) -> None:
        guide = text("docs/consumer-guide.md")
        self.assertIn("Agent Skill, Website, or Web application repository", guide)
        self.assertIn("guides/website-webapp-selection.md", guide)
        self.assertIn('"recipe": "website"', guide)
        self.assertIn('"recipe": "webapp"', guide)
        self.assertIn("product identity", guide)

    def test_concepts_guide_describes_website_and_webapp_as_sibling_artifacts(self) -> None:
        guide = text("docs/guides/composition-concepts.md")
        for expected in (
            "Website",
            "Web application",
            "foundation.web",
            "artifact.website-core",
            "artifact.webapp-core",
            "site structure",
            "surfaces",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, guide)
        self.assertNotIn("A future Website recipe", guide)
        self.assertNotIn("minimal static browser application", guide)

    def test_publication_boundary_describes_current_three_artifact_provider_surface(self) -> None:
        publication = text("docs/publication-catalog.md")
        for expected in (
            "Agent Skill",
            "Website",
            "Web application",
            "foundation.web",
            "Website domain contracts",
            "Webapp domain contracts",
            "three production recipes",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, publication)

        catalog = json.loads(text("docs/publication-catalog.json"))
        published = {entry["source"] for entry in catalog["documents"]}
        self.assertIn("docs/guides/website-webapp-selection.md", published)
        self.assertIn("docs/guides/website-product-walkthrough.md", published)

    def test_architecture_and_schema_guides_match_four_component_roles(self) -> None:
        catalog_architecture = text("docs/architecture/catalog.md")
        composition_model = text("docs/architecture/composition-model.md")
        schema_guide = text("schemas/README.md")

        self.assertIn("`website`", catalog_architecture)
        self.assertIn("foundation", catalog_architecture.lower())
        self.assertIn("Website", composition_model)
        for role in ("foundation", "artifact", "capability", "lifecycle"):
            with self.subTest(role=role):
                self.assertIn(role, schema_guide)

    def test_glossary_examples_include_website_without_renaming_stable_ids(self) -> None:
        glossary = json.loads(text("docs/glossary.yml"))
        terms = {entry["id"]: entry for entry in glossary["terms"]}
        artifact_usage = terms["templates-composition-artifact-component"]["repository_usage"]
        runtime_usage = terms["templates-runtime-decision-record"]["repository_usage"]
        self.assertIn("Website", artifact_usage)
        self.assertIn("Website", runtime_usage)
        self.assertIn("templates-webapp-product-mode", terms)

    def test_japanese_reader_surfaces_keep_the_same_artifact_selection_model(self) -> None:
        selection_surfaces = (
            "translations/ja/README.md",
            "translations/ja/docs/consumer-guide.md",
            "translations/ja/docs/guides/composition-concepts.md",
            "translations/ja/docs/publication-catalog.md",
            "translations/ja/docs/architecture/catalog.md",
            "translations/ja/docs/architecture/composition-model.md",
        )
        for path in selection_surfaces:
            with self.subTest(path=path):
                translated = text(path)
                self.assertIn("Website", translated)
                self.assertIn("Web", translated)

        schema_guide = text("translations/ja/schemas/README.md")
        for role in ("foundation", "artifact", "capability", "lifecycle"):
            with self.subTest(role=role):
                self.assertIn(role, schema_guide)


if __name__ == "__main__":
    unittest.main()

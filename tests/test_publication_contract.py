from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_publication.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("composition_publication_validator", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompositionPublicationContractTests(unittest.TestCase):
    def test_recipe_assets_are_a_closed_machine_inventory(self):
        catalog = json.loads((ROOT / "docs/publication-catalog.json").read_text())
        assets = catalog["assets"]
        recipes = {path.relative_to(ROOT).as_posix() for path in (ROOT / "recipes").glob("*.json")}
        selected = [item for item in assets if item["source"] == "recipes"
                    or item["source"].startswith("recipes/")]
        self.assertEqual({item["source"] for item in selected}, recipes)
        self.assertTrue(all(item["destination"] == item["source"] for item in selected))
        # Future navigation at any depth must not fall under an asset root.
        for navigation in ("recipes/index.md", "recipes/nested/index.md"):
            self.assertFalse(any(navigation == item["source"]
                                 or navigation.startswith(item["source"] + "/")
                                 for item in assets))

    def test_provider_publication_is_valid(self):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Composition publication validation: OK", result.stdout)

    def test_catalog_is_composition_owned_and_has_one_home(self):
        validator = load_validator()
        catalog = validator.load_publication_catalog()
        homes = [entry for entry in catalog.documents if entry.home]
        self.assertEqual(len(homes), 1)
        self.assertEqual(homes[0].source.as_posix(), "README.md")
        sources = {entry.source.as_posix() for entry in catalog.documents}
        self.assertIn("docs/consumer-guide.md", sources)
        self.assertIn("docs/reference/composer.md", sources)
        self.assertIn("docs/migrations/composition-authority-migration.md", sources)
        self.assertNotIn("docs/migrations/pr2-skill-capabilities.md", sources)
        self.assertNotIn("docs/migrations/pr3-webapp-lifecycle.md", sources)
        self.assertIn("components/artifact.skill-core/files/SKILL.md", sources)
        self.assertIn("components/artifact.webapp-core/files/TEMPLATE.md", sources)
        self.assertIn(
            "components/lifecycle.contract-evolution/files/docs/architecture/contract-evolution.md",
            sources,
        )
        self.assertNotIn("template/SKILL.md", sources)
        self.assertNotIn("template/README.md", sources)
        self.assertEqual(catalog.glossary_source.as_posix(), "docs/glossary.yml")

    def test_publication_boundary_does_not_exclude_or_disavow_catalog_documents(self):
        """Keep the human boundary contract aligned with the catalog allowlist."""
        validator = load_validator()
        catalog = validator.load_publication_catalog()
        published = {entry.source.as_posix() for entry in catalog.documents}
        boundary = (ROOT / "docs" / "publication-catalog.md").read_text(encoding="utf-8")

        exclusions_start = boundary.index("The current explicit exclusions are:")
        exclusions_end = boundary.index(
            "Provider-owned translation derivatives", exclusions_start
        )
        exclusion_paths = {
            path
            for line in boundary[exclusions_start:exclusions_end].splitlines()
            if line.startswith("- ")
            for parenthetical in re.findall(r"\(([^)]*)\)", line)
            for path in re.findall(r"`([^`]+\.md)`", parenthetical)
        }
        self.assertFalse(
            published & exclusion_paths,
            "publication-boundary explicit exclusions overlap published catalog documents",
        )

        disavowed_paths = set(
            re.findall(
                r"`([^`]+\.md)`[^.]*?\bnot reader-facing(?: publication)?\b",
                boundary,
                flags=re.IGNORECASE,
            )
        )
        self.assertFalse(
            published & disavowed_paths,
            "publication-boundary disavows published catalog documents",
        )

    def test_consumer_docs_are_primary_entry_points(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[Using Composition](docs/consumer-guide.md)", readme)
        self.assertIn("[Composer reference](docs/reference/composer.md)", readme)

        index = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
        consumer_position = index.index("[Using Composition](consumer-guide.md)")
        reference_position = index.index("[Composer reference](reference/composer.md)")
        architecture_position = index.index("## Composition architecture")
        self.assertLess(consumer_position, architecture_position)
        self.assertLess(reference_position, architecture_position)

    def test_landing_page_separates_current_state_from_migration_history(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith("# Composition\n"))
        self.assertNotIn("## Migration state", readme)
        for stage_label in ("PR1", "PR2", "PR3", "PR4", "PR5", "Site PR #270"):
            with self.subTest(stage_label=stage_label):
                self.assertNotIn(stage_label, readme)
        self.assertIn(
            "[Composition authority migration history](docs/migrations/composition-authority-migration.md)",
            readme,
        )
        self.assertNotIn("docs/migrations/pr2-skill-capabilities.md", readme)
        self.assertNotIn("docs/migrations/pr3-webapp-lifecycle.md", readme)

        index = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
        self.assertIn("## Historical provenance", index)
        self.assertIn(
            "[Composition authority migration](migrations/composition-authority-migration.md)",
            index,
        )
        self.assertNotIn("migrations/pr2-skill-capabilities.md", index)
        self.assertNotIn("migrations/pr3-webapp-lifecycle.md", index)
        history = (
            ROOT / "docs" / "migrations" / "composition-authority-migration.md"
        ).read_text(encoding="utf-8")
        self.assertIn("https://github.com/TakashiSasaki/templates/pull/265", history)
        self.assertIn("https://github.com/TakashiSasaki/templates/pull/277", history)
        self.assertNotIn("](pr2-skill-capabilities.md)", history)
        self.assertNotIn("](pr3-webapp-lifecycle.md)", history)

    def test_catalog_guide_uses_current_managed_lifecycle(self):
        guide = (ROOT / "catalog" / "README.md").read_text(encoding="utf-8")
        for retired_claim in (
            "schema-v1 lock",
            "outside the composer MVP's apply contract",
            "causes update refusal",
        ):
            with self.subTest(retired_claim=retired_claim):
                self.assertNotIn(retired_claim, guide)
        self.assertIn("lock schema v2", guide)
        self.assertIn("`update` preserves", guide)
        self.assertIn("`upgrade` accepts", guide)

    def test_only_root_execution_state_directories_are_ignored(self):
        validator = load_validator()
        self.assertTrue(
            validator.is_ignored_root_execution_path(
                PurePosixPath(".venv/lib/README.md")
            )
        )
        self.assertTrue(
            validator.is_ignored_root_execution_path(
                PurePosixPath(".pytest_cache/README.md")
            )
        )
        self.assertTrue(
            validator.is_ignored_root_execution_path(
                PurePosixPath(".integration-publication-protocol/scripts/README.md")
            )
        )
        self.assertFalse(
            validator.is_ignored_root_execution_path(
                PurePosixPath("components/example/files/.venv/README.md")
            )
        )
        self.assertFalse(
            validator.is_ignored_root_execution_path(
                PurePosixPath("docs/__pycache__/README.md")
            )
        )
        self.assertFalse(
            validator.is_ignored_root_execution_path(
                PurePosixPath("node_modules/README.md")
            )
        )

    def test_unclassified_markdown_fails_closed(self):
        validator = load_validator()
        published = {PurePosixPath("README.md")}
        discovered = published | {PurePosixPath("docs/guides/new-guide.md")}
        with self.assertRaises(validator.PublicationError) as raised:
            validator.validate_markdown_partition(published, set(), set(), discovered)
        self.assertIn("lacks explicit publication classification", str(raised.exception))
        self.assertIn("docs/guides/new-guide.md", str(raised.exception))

    def test_markdown_cannot_be_both_published_and_excluded(self):
        validator = load_validator()
        source = PurePosixPath("README.md")
        with self.assertRaises(validator.PublicationError) as raised:
            validator.validate_markdown_partition({source}, {source}, set(), {source})
        self.assertIn("both published and explicitly excluded", str(raised.exception))

    def test_markdown_cannot_be_both_published_and_translation_declared(self):
        validator = load_validator()
        source = PurePosixPath("README.md")
        with self.assertRaises(validator.PublicationError) as raised:
            validator.validate_markdown_partition({source}, set(), {source}, {source})
        self.assertIn("both published and translation-declared", str(raised.exception))

    def test_markdown_cannot_be_both_excluded_and_translation_declared(self):
        validator = load_validator()
        source = PurePosixPath("translations/ja/README.md")
        with self.assertRaises(validator.PublicationError) as raised:
            validator.validate_markdown_partition(set(), {source}, {source}, {source})
        self.assertIn(
            "both explicitly excluded and translation-declared",
            str(raised.exception),
        )

    def test_classification_cannot_reference_undiscovered_markdown(self):
        validator = load_validator()
        with self.assertRaises(validator.PublicationError) as raised:
            validator.validate_markdown_partition(
                {PurePosixPath("README.md")},
                {PurePosixPath("removed/README.md")},
                set(),
                {PurePosixPath("README.md")},
            )
        self.assertIn("references undiscovered source", str(raised.exception))

    def test_glossary_is_strict_json_yaml_subset_and_drops_retired_copy_model(self):
        raw = (ROOT / "docs" / "glossary.yml").read_text(encoding="utf-8")
        self.assertTrue(raw.lstrip().startswith("{"))
        glossary = json.loads(raw)
        ids = {term["id"] for term in glossary["terms"]}
        self.assertIn("templates-skill-profile", ids)
        self.assertIn("templates-composition-component", ids)
        self.assertIn("templates-contract-manifest", ids)
        self.assertIn("templates-implementation-runtime", ids)
        self.assertIn("templates-runtime-decision-record", ids)
        for term_id in (
            "templates-composition-material-ownership",
            "templates-composition-component-owner",
            "templates-composition-ownership-mode",
            "templates-composition-managed-material",
            "templates-composition-seed-material",
            "templates-composition-generated-material",
        ):
            with self.subTest(term_id=term_id):
                self.assertIn(term_id, ids)
        for term in glossary["terms"]:
            for related in term.get("related_terms", []):
                if related.startswith("templates-composition-"):
                    with self.subTest(term=term["id"], related=related):
                        self.assertIn(related, ids)
        self.assertNotIn("templates-webapp-template-distribution-artifact", ids)
        self.assertNotIn("templates-skill-mcp-extension", ids)



if __name__ == "__main__":
    unittest.main()

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
GUIDED_INDEX_PATHS = [
    "components/artifact.skill-core/files/docs/index.md",
    "components/artifact.webapp-core/files/docs/index.md",
    "docs/index.md",
]
GUIDED_LINK = re.compile(r"^- \[[^\]]+\]\(.+\)[ \t]+[-–—][ \t]+\S.+$")
LINK_TARGET = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def load_validator():
    spec = importlib.util.spec_from_file_location("composition_publication_validator", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompositionPublicationContractTests(unittest.TestCase):
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

    def test_publication_assets_cover_closed_production_authorities(self):
        validator = load_validator()
        catalog = validator.load_publication_catalog()
        exclusions = validator.parse_publication_classification()
        validator.validate_composition_catalog_declarations(catalog)
        validator.validate_reader_coverage(catalog)
        validator.validate_markdown_classification(catalog, exclusions)
        validator.validate_machine_coverage(catalog)
        self.assertEqual(catalog.glossary_source.as_posix(), "docs/glossary.yml")

    def test_all_repository_markdown_is_published_or_explicitly_excluded(self):
        validator = load_validator()
        catalog = validator.load_publication_catalog()
        exclusions = validator.parse_publication_classification()
        published = {entry.source for entry in catalog.documents}
        discovered = validator.discover_repository_markdown()
        translation_manifest = json.loads(
            (ROOT / "translations" / "manifest.json").read_text(encoding="utf-8")
        )
        translation_exclusions = {
            PurePosixPath(entry["translation"])
            for entry in translation_manifest["translations"]
        }
        expected_exclusions = {
            PurePosixPath("components/artifact.skill-core/files/AGENTS.md"),
            PurePosixPath("docs/migrations/pr2-skill-capabilities.md"),
            PurePosixPath("docs/migrations/pr3-webapp-lifecycle.md"),
            PurePosixPath("examples/README.md"),
            PurePosixPath("release/README.md"),
            PurePosixPath("skills/composition/SKILL.md"),
            PurePosixPath("translations/README.md"),
        } | translation_exclusions

        self.assertEqual(published | set(exclusions), discovered)
        self.assertFalse(published & set(exclusions))
        self.assertEqual(set(exclusions), expected_exclusions)
        self.assertTrue(all(reason.strip() for reason in exclusions.values()))

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
                PurePosixPath(".site-publication-protocol/scripts/README.md")
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
            validator.validate_markdown_partition(published, set(), discovered)
        self.assertIn("lacks explicit publication classification", str(raised.exception))
        self.assertIn("docs/guides/new-guide.md", str(raised.exception))

    def test_markdown_cannot_be_both_published_and_excluded(self):
        validator = load_validator()
        source = PurePosixPath("README.md")
        with self.assertRaises(validator.PublicationError) as raised:
            validator.validate_markdown_partition({source}, {source}, {source})
        self.assertIn("both published and explicitly excluded", str(raised.exception))

    def test_classification_cannot_reference_undiscovered_markdown(self):
        validator = load_validator()
        with self.assertRaises(validator.PublicationError) as raised:
            validator.validate_markdown_partition(
                {PurePosixPath("README.md")},
                {PurePosixPath("removed/README.md")},
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

    def test_guided_indexes_use_restricted_navigation_shape(self):
        index_paths = sorted(ROOT.rglob("index.md"))
        index_paths = [
            path
            for path in index_paths
            if ".site-publication-protocol" not in path.relative_to(ROOT).parts
        ]
        self.assertEqual(
            [path.relative_to(ROOT).as_posix() for path in index_paths],
            GUIDED_INDEX_PATHS,
        )
        for index_path in index_paths:
            for number, raw_line in enumerate(
                index_path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                line = raw_line.strip()
                if not line:
                    continue
                with self.subTest(
                    path=index_path.relative_to(ROOT).as_posix(),
                    line=number,
                ):
                    self.assertTrue(
                        line.startswith("#") or GUIDED_LINK.fullmatch(line),
                        f"unsupported guided index content at "
                        f"{index_path.relative_to(ROOT)}:{number}: {raw_line!r}",
                    )

    def test_guided_index_local_links_remain_inside_source_and_exist(self):
        for relative_index in GUIDED_INDEX_PATHS:
            index_path = ROOT / relative_index
            links = LINK_TARGET.findall(index_path.read_text(encoding="utf-8"))
            self.assertTrue(links, relative_index)
            for target in links:
                with self.subTest(index=relative_index, target=target):
                    self.assertFalse(target.startswith(("http://", "https://", "/")))
                    path = (index_path.parent / target).resolve()
                    path.relative_to(ROOT.resolve())
                    self.assertTrue(path.exists(), target)
                    self.assertFalse(path.is_symlink(), target)


if __name__ == "__main__":
    unittest.main()

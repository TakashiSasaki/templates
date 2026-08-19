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
        catalog = json.loads((ROOT / "docs" / "publication-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"], 3)
        homes = [entry for entry in catalog["documents"] if entry["home"]]
        self.assertEqual(len(homes), 1)
        self.assertEqual(homes[0]["source"], "README.md")
        sources = {entry["source"] for entry in catalog["documents"]}
        self.assertIn("components/artifact.skill-core/files/SKILL.md", sources)
        self.assertIn("components/artifact.webapp-core/files/TEMPLATE.md", sources)
        self.assertIn("components/lifecycle.contract-evolution/files/docs/architecture/contract-evolution.md", sources)
        self.assertNotIn("template/SKILL.md", sources)
        self.assertNotIn("template/README.md", sources)

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
        documents, assets, glossary = validator.parse_catalog()
        exclusions = validator.parse_publication_classification()
        validator.validate_reader_coverage(documents)
        validator.validate_markdown_classification(documents, exclusions)
        validator.validate_machine_coverage(assets)
        self.assertEqual(glossary.as_posix(), "docs/glossary.yml")

    def test_all_repository_markdown_is_published_or_explicitly_excluded(self):
        validator = load_validator()
        documents, _, _ = validator.parse_catalog()
        exclusions = validator.parse_publication_classification()
        published = {entry["source"] for entry in documents.values()}
        discovered = validator.discover_repository_markdown()

        self.assertEqual(published | set(exclusions), discovered)
        self.assertFalse(published & set(exclusions))
        self.assertEqual(
            set(exclusions),
            {
                PurePosixPath("components/artifact.skill-core/files/AGENTS.md"),
                PurePosixPath("examples/README.md"),
            },
        )
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
        self.assertNotIn("templates-webapp-template-distribution-artifact", ids)
        self.assertNotIn("templates-skill-mcp-extension", ids)

    def test_guided_indexes_use_restricted_navigation_shape(self):
        index_paths = sorted(ROOT.rglob("index.md"))
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

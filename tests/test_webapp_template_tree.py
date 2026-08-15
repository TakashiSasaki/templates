from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.generate_repository_trees import RepositoryTreeError
from scripts.generate_webapp_template_tree import generate
from scripts.prepare_repository_tree_publication import (
    WEBAPP_TEMPLATE_DOCUMENT,
    WEBAPP_TEMPLATE_NAVIGATION,
)


ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE = ROOT / "MAINTENANCE.md"
REPOSITORY = "TakashiSasaki/templates"


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def initialize_webapp(root: Path, *, with_template: bool = True) -> str:
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    if with_template:
        (root / "template").mkdir()
        (root / "template" / "README.md").write_text("# Template\n", encoding="utf-8")
        (root / "template" / "contracts").mkdir()
        (root / "template" / "contracts" / "manifest.json").write_text(
            "{}\n",
            encoding="utf-8",
        )
    write_json(
        root / "docs" / "publication-catalog.json",
        {
            "schema_version": 3,
            "documents": [
                {
                    "id": "overview",
                    "source": "template/README.md" if with_template else "README.md",
                    "optional": False,
                    "home": True,
                }
            ],
            "assets": [],
        },
    )
    if not with_template:
        (root / "README.md").write_text("# Source\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "fixture")
    return git(root, "rev-parse", "HEAD")


def prepare_site_root(root: Path) -> None:
    write_json(
        root / "site-manifest.json",
        {
            "schema_version": 2,
            "home": {"publication": "site", "document": "portal-home"},
            "navigation": [
                {
                    "title": "Web application",
                    "publication": "webapp",
                    "document": "overview",
                    "destination": "webapp/index.md",
                }
            ],
        },
    )


def prepare_output_root(root: Path) -> None:
    root.mkdir()
    (root / "zensical.toml").write_text(
        '[project]\nsite_url = "https://example.invalid/templates/"\n',
        encoding="utf-8",
    )
    page = root / "docs" / "repository-trees" / "webapp" / "template.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "# Template tree\n\n<!-- GENERATED_WEBAPP_TEMPLATE_TREE -->\n",
        encoding="utf-8",
    )
    index = root / "docs" / "repository-trees" / "index.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        "# Trees\n\n<!-- GENERATED_WEBAPP_TEMPLATE_SUMMARY -->\n",
        encoding="utf-8",
    )


class WebappTemplateTreeTests(unittest.TestCase):
    def test_generation_renders_the_template_subtree_as_copy_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            webapp = temporary / "webapp"
            revision = initialize_webapp(webapp)
            site_root = temporary / "site"
            site_root.mkdir()
            prepare_site_root(site_root)
            output_root = temporary / "build"
            prepare_output_root(output_root)

            message = generate(REPOSITORY, site_root, output_root, webapp)

            page = (
                output_root
                / "docs"
                / "repository-trees"
                / "webapp"
                / "template.md"
            ).read_text(encoding="utf-8")
            index = (
                output_root / "docs" / "repository-trees" / "index.md"
            ).read_text(encoding="utf-8")

            self.assertIn(f"webapp template: 2 files at {revision}", message)
            self.assertIn("**Copyable root:**", page)
            self.assertIn(f"tree/{revision}/template", page)
            self.assertIn("contracts/", page)
            self.assertIn("manifest.json", page)
            self.assertIn("/templates/webapp/", page)
            self.assertNotIn("GENERATED_WEBAPP_TEMPLATE_TREE", page)
            self.assertNotIn("repository-file-viewer", page)
            self.assertNotIn("repository-file-preview-link", page)
            self.assertIn("Web application copyable template", index)
            self.assertIn(revision, index)
            self.assertNotIn("GENERATED_WEBAPP_TEMPLATE_SUMMARY", index)

    def test_missing_template_subtree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            webapp = temporary / "webapp"
            initialize_webapp(webapp, with_template=False)
            site_root = temporary / "site"
            site_root.mkdir()
            prepare_site_root(site_root)
            output_root = temporary / "build"
            prepare_output_root(output_root)

            with self.assertRaisesRegex(
                RepositoryTreeError,
                "does not contain a tracked template directory",
            ):
                generate(REPOSITORY, site_root, output_root, webapp)

    def test_preparation_contract_registers_the_nested_page_additively(self) -> None:
        self.assertEqual(
            "repository-tree-webapp-template",
            WEBAPP_TEMPLATE_DOCUMENT["id"],
        )
        self.assertEqual(
            "docs/repository-trees/webapp/template.md",
            WEBAPP_TEMPLATE_DOCUMENT["source"],
        )
        self.assertEqual(
            "repository-trees/webapp/template.md",
            WEBAPP_TEMPLATE_NAVIGATION["destination"],
        )
        self.assertEqual(
            "Web application copyable template",
            WEBAPP_TEMPLATE_NAVIGATION["title"],
        )

    def test_maintenance_documents_both_copyable_tree_pipelines(self) -> None:
        maintenance = MAINTENANCE.read_text(encoding="utf-8")

        self.assertRegex(
            maintenance,
            r"exactly six generated\s+document declarations",
        )
        self.assertIn("`repository-trees/skill/template.md`", maintenance)
        self.assertIn("`repository-trees/webapp/template.md`", maintenance)
        self.assertIn("## Skill copyable-template tree generation", maintenance)
        self.assertIn("does not receive an inline preview panel", maintenance)

        commands = (
            "python site/scripts/generate_repository_trees.py",
            "python site/scripts/generate_skill_template_tree.py",
            "python site/scripts/generate_webapp_template_tree.py",
            "python site/scripts/generate_repository_file_previews.py",
            "zensical build",
        )
        positions = [maintenance.index(command) for command in commands]
        self.assertEqual(sorted(positions), positions)


if __name__ == "__main__":
    unittest.main()

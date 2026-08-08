from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.generate_repository_trees import RepositoryTreeError
from scripts.generate_skill_template_tree import generate
from scripts.prepare_repository_tree_publication import (
    SKILL_TEMPLATE_DOCUMENT,
    SKILL_TEMPLATE_NAVIGATION,
    prepare,
)


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


def initialize_skill(root: Path, *, with_template: bool = True) -> str:
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    if with_template:
        (root / "template").mkdir()
        (root / "template" / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
        (root / "template" / "references").mkdir()
        (root / "template" / "references" / "README.md").write_text(
            "# References\n",
            encoding="utf-8",
        )
    else:
        (root / "README.md").write_text("# Source\n", encoding="utf-8")
    write_json(
        root / "docs" / "publication-catalog.json",
        {
            "schema_version": 1,
            "documents": [
                {
                    "id": "overview",
                    "source": "template/SKILL.md" if with_template else "README.md",
                    "optional": False,
                    "home": True,
                }
            ],
        },
    )
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
                    "title": "Skill",
                    "publication": "skill",
                    "document": "overview",
                    "destination": "skill/index.md",
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
    page = root / "docs" / "repository-trees" / "skill" / "template.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "# Template tree\n\n<!-- GENERATED_SKILL_TEMPLATE_TREE -->\n",
        encoding="utf-8",
    )
    overview = root / "docs" / "repository-trees" / "overview.md"
    overview.parent.mkdir(parents=True, exist_ok=True)
    overview.write_text(
        "# Trees\n\n<!-- GENERATED_SKILL_TEMPLATE_SUMMARY -->\n",
        encoding="utf-8",
    )


class SkillTemplateTreeTests(unittest.TestCase):
    def test_generation_renders_the_template_subtree_as_copy_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            skill = temporary / "skill"
            revision = initialize_skill(skill)
            site_root = temporary / "site"
            site_root.mkdir()
            prepare_site_root(site_root)
            output_root = temporary / "build"
            prepare_output_root(output_root)

            message = generate(REPOSITORY, site_root, output_root, skill)

            page = (
                output_root
                / "docs"
                / "repository-trees"
                / "skill"
                / "template.md"
            ).read_text(encoding="utf-8")
            overview = (
                output_root / "docs" / "repository-trees" / "overview.md"
            ).read_text(encoding="utf-8")

            self.assertIn(f"skill template: 2 files at {revision}", message)
            self.assertIn("**Copyable root:**", page)
            self.assertIn(f"tree/{revision}/template", page)
            self.assertIn("references/", page)
            self.assertIn("SKILL.md", page)
            self.assertIn("/templates/skill/", page)
            self.assertNotIn("GENERATED_SKILL_TEMPLATE_TREE", page)
            self.assertNotIn("repository-file-viewer", page)
            self.assertNotIn("repository-file-preview-link", page)
            self.assertIn("Skill copyable template", overview)
            self.assertIn(revision, overview)
            self.assertNotIn("GENERATED_SKILL_TEMPLATE_SUMMARY", overview)

    def test_missing_template_subtree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            skill = temporary / "skill"
            initialize_skill(skill, with_template=False)
            site_root = temporary / "site"
            site_root.mkdir()
            prepare_site_root(site_root)
            output_root = temporary / "build"
            prepare_output_root(output_root)

            with self.assertRaisesRegex(
                RepositoryTreeError,
                "does not contain a tracked template directory",
            ):
                generate(REPOSITORY, site_root, output_root, skill)

    def test_preparation_contract_registers_the_nested_page_additively(self) -> None:
        self.assertEqual(
            "repository-tree-skill-template",
            SKILL_TEMPLATE_DOCUMENT["id"],
        )
        self.assertEqual(
            "docs/repository-trees/skill/template.md",
            SKILL_TEMPLATE_DOCUMENT["source"],
        )
        self.assertEqual(
            "repository-trees/skill/template.md",
            SKILL_TEMPLATE_NAVIGATION["destination"],
        )
        self.assertEqual(
            "Skill copyable template",
            SKILL_TEMPLATE_NAVIGATION["title"],
        )

    def test_preparation_registers_skill_page_when_template_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            site_root = temporary / "site"
            site_root.mkdir()
            write_json(
                site_root / "docs" / "publication-catalog.json",
                {
                    "schema_version": 1,
                    "documents": [
                        {
                            "id": "portal-home",
                            "source": "docs/landing.md",
                            "optional": False,
                            "home": True,
                        }
                    ],
                },
            )
            (site_root / "docs" / "index.md").write_text(
                "# Site documentation\n\n* [Landing](landing.md) - Portal landing.\n",
                encoding="utf-8",
            )
            (site_root / "docs" / "landing.md").write_text(
                "# Portal\n", encoding="utf-8"
            )
            write_json(
                site_root / "site-manifest.json",
                {
                    "schema_version": 2,
                    "home": {"publication": "site", "document": "portal-home"},
                    "navigation": [
                        {
                            "title": "Documentation portal",
                            "publication": "site",
                            "document": "portal-home",
                            "destination": "index.md",
                        }
                    ],
                },
            )
            (site_root / "zensical.template.toml").write_text(
                "nav = __GENERATED_NAV__\n", encoding="utf-8"
            )
            tree_root = site_root / "docs" / "repository-trees"
            tree_root.mkdir(parents=True)
            (tree_root / "index.md").write_text(
                "# Trees\n\n* [Overview](overview.md) - Generated overview.\n",
                encoding="utf-8",
            )
            (tree_root / "overview.md").write_text(
                "# Trees\n\n<!-- GENERATED_REPOSITORY_TREE_INDEX -->\n",
                encoding="utf-8",
            )
            for publication in ("skill", "policy", "webapp"):
                (tree_root / f"{publication}.md").write_text(
                    f"# {publication}\n", encoding="utf-8"
                )
            for publication, marker in (
                ("skill", "GENERATED_SKILL_TEMPLATE_TREE"),
                ("webapp", "GENERATED_WEBAPP_TEMPLATE_TREE"),
            ):
                page = tree_root / publication / "template.md"
                page.parent.mkdir(parents=True)
                page.write_text(f"<!-- {marker} -->\n", encoding="utf-8")

            output_root = temporary / "prepared"
            prepare(site_root, output_root)

            catalog = json.loads(
                (output_root / "docs" / "publication-catalog.json").read_text(
                    encoding="utf-8"
                )
            )
            manifest = json.loads(
                (output_root / "site-manifest.json").read_text(encoding="utf-8")
            )
            self.assertIn(
                "repository-tree-skill-template",
                {document["id"] for document in catalog["documents"]},
            )
            self.assertIn(
                "repository-trees/skill/template.md",
                [
                    node.get("destination")
                    for node in manifest["navigation"]
                    if isinstance(node, dict)
                ],
            )


if __name__ == "__main__":
    unittest.main()

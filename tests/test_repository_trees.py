from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.generate_repository_trees import (
    RepositoryTreeError,
    build_tree,
    entry_label,
    generate,
    parse_ls_tree,
)
from scripts.prepare_repository_tree_publication import (
    PreparationError,
    TREE_DOCUMENTS,
    prepare,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
POLICY = ROOT / "PUBLISHING.md"
TREE_TEMPLATES = ROOT / "docs/repository-trees"


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process.stdout.strip()


class RepositoryTreeGenerationTests(unittest.TestCase):
    def make_publication(self, root: Path, name: str) -> str:
        root.mkdir()
        run_git(root, "init", "--quiet")
        run_git(root, "config", "user.email", "tests@example.invalid")
        run_git(root, "config", "user.name", "Repository tree tests")

        (root / "docs").mkdir()
        (root / "docs/publication-catalog.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "documents": [
                        {
                            "id": "overview",
                            "source": "README.md",
                            "optional": False,
                            "home": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        (root / "nested").mkdir()
        (root / "nested/a & b.txt").write_text("tracked\n", encoding="utf-8")
        (root / "nested/<script>.txt").write_text("escaped\n", encoding="utf-8")
        os.symlink("README.md", root / "readme-link")
        (root / "untracked-secret.txt").write_text("not listed\n", encoding="utf-8")

        run_git(
            root,
            "add",
            "README.md",
            "docs/publication-catalog.json",
            "nested",
            "readme-link",
        )
        run_git(root, "commit", "--quiet", "--message", "fixture")
        return run_git(root, "rev-parse", "HEAD")

    def make_site(self, root: Path) -> None:
        root.mkdir()
        (root / "site-manifest.json").write_text(
            json.dumps(
                {
                    "navigation": [
                        {
                            "title": "Skill",
                            "publication": "skill",
                            "document": "overview",
                            "destination": "skill/index.md",
                        },
                        {
                            "title": "Policy",
                            "publication": "policy",
                            "document": "overview",
                            "destination": "policy/index.md",
                        },
                        {
                            "title": "Web application",
                            "publication": "webapp",
                            "document": "overview",
                            "destination": "webapp/index.md",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

    def make_templates(self, output_root: Path) -> None:
        tree_root = output_root / "docs/repository-trees"
        tree_root.mkdir(parents=True)
        (output_root / "zensical.toml").write_text(
            '[project]\nsite_url = "https://takashisasaki.github.io/templates/"\n',
            encoding="utf-8",
        )
        (tree_root / "index.md").write_text(
            "# Repository trees\n\n<!-- GENERATED_REPOSITORY_TREE_INDEX -->\n",
            encoding="utf-8",
        )
        for publication in ("skill", "policy", "webapp"):
            (tree_root / f"{publication}.md").write_text(
                f"# {publication}\n\n"
                f"<!-- GENERATED_REPOSITORY_TREE:{publication} -->\n",
                encoding="utf-8",
            )

    def test_generation_uses_tracked_entries_and_immutable_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site_root = root / "site"
            output_root = root / "build"
            self.make_site(site_root)
            self.make_templates(output_root)

            publications = {}
            revisions = {}
            for publication in ("skill", "policy", "webapp"):
                publication_root = root / publication
                revisions[publication] = self.make_publication(
                    publication_root,
                    publication,
                )
                publications[publication] = publication_root

            generate(
                "TakashiSasaki/templates",
                site_root,
                output_root,
                publications,
            )

            skill_page = (
                output_root / "docs/repository-trees/skill.md"
            ).read_text(encoding="utf-8")
            index_page = (
                output_root / "docs/repository-trees/index.md"
            ).read_text(encoding="utf-8")

            self.assertIn(revisions["skill"], skill_page)
            self.assertIn(
                f"https://github.com/TakashiSasaki/templates/tree/"
                f"{revisions['skill']}",
                skill_page,
            )
            self.assertIn("a%20%26%20b.txt", skill_page)
            self.assertIn("%3Cscript%3E.txt", skill_page)
            self.assertNotIn("<script>.txt", skill_page)
            self.assertIn("&lt;script&gt;.txt", skill_page)
            self.assertIn("(symlink)", skill_page)
            self.assertNotIn("untracked-secret.txt", skill_page)
            self.assertIn('href="/templates/skill/"', skill_page)
            self.assertIn(">source</a>", skill_page)
            self.assertIn("[Skill](skill.md)", index_page)
            self.assertIn(revisions["policy"], index_page)
            self.assertNotIn("GENERATED_REPOSITORY_TREE", skill_page)
            self.assertNotIn("GENERATED_REPOSITORY_TREE_INDEX", index_page)

    def test_gitlink_entries_are_not_treated_as_files(self) -> None:
        object_id = b"1" * 40
        entries = parse_ls_tree(
            b"040000 tree " + object_id + b"\tvendor\0"
            b"160000 commit " + object_id + b"\tvendor/dependency\0"
        )
        tree = build_tree(entries)
        gitlink = tree.children[b"vendor"].children[b"dependency"]

        self.assertEqual(entry_label(gitlink), "gitlink")
        self.assertFalse(gitlink.is_directory)

    def test_generation_requires_all_three_provider_publications(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site_root = root / "site"
            output_root = root / "build"
            self.make_site(site_root)
            self.make_templates(output_root)

            with self.assertRaisesRegex(
                RepositoryTreeError,
                "exactly skill, policy, and webapp",
            ):
                generate(
                    "TakashiSasaki/templates",
                    site_root,
                    output_root,
                    {"skill": root},
                )


class RepositoryTreePreparationTests(unittest.TestCase):
    def make_site_source(self, root: Path) -> None:
        (root / "docs/repository-trees").mkdir(parents=True)
        (root / "docs/index.md").write_text("# Portal\n", encoding="utf-8")
        (root / "docs/publication-catalog.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "documents": [
                        {
                            "id": "portal-home",
                            "source": "docs/index.md",
                            "optional": False,
                            "home": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "site-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "home": {
                        "publication": "site",
                        "document": "portal-home",
                    },
                    "navigation": [
                        {
                            "title": "Documentation portal",
                            "publication": "site",
                            "document": "portal-home",
                            "destination": "index.md",
                        },
                        {
                            "title": "Skill",
                            "children": [
                                {
                                    "title": "Overview",
                                    "publication": "skill",
                                    "document": "overview",
                                    "destination": "skill/index.md",
                                }
                            ],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "zensical.template.toml").write_text(
            "nav = __GENERATED_NAV__\n",
            encoding="utf-8",
        )
        (root / "docs/repository-trees/index.md").write_text(
            "# Repository trees\n\n<!-- GENERATED_REPOSITORY_TREE_INDEX -->\n",
            encoding="utf-8",
        )
        for publication in ("skill", "policy", "webapp"):
            (root / f"docs/repository-trees/{publication}.md").write_text(
                f"# {publication}\n\n"
                f"<!-- GENERATED_REPOSITORY_TREE:{publication} -->\n",
                encoding="utf-8",
            )
        template_page = root / "docs/repository-trees/webapp/template.md"
        template_page.parent.mkdir(parents=True)
        template_page.write_text(
            "# Web application copyable template\n\n"
            "<!-- GENERATED_WEBAPP_TEMPLATE_TREE -->\n",
            encoding="utf-8",
        )

    def test_preparation_augments_catalog_and_navigation_without_mutating_source(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site_root = root / "site"
            output_root = root / "prepared"
            site_root.mkdir()
            self.make_site_source(site_root)

            source_catalog = (
                site_root / "docs/publication-catalog.json"
            ).read_text(encoding="utf-8")
            source_manifest = (
                site_root / "site-manifest.json"
            ).read_text(encoding="utf-8")

            prepare(site_root, output_root)

            catalog = json.loads(
                (output_root / "docs/publication-catalog.json").read_text(
                    encoding="utf-8"
                )
            )
            manifest = json.loads(
                (output_root / "site-manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(
                {document["id"] for document in TREE_DOCUMENTS},
                {
                    "repository-trees",
                    "repository-tree-skill",
                    "repository-tree-policy",
                    "repository-tree-webapp",
                },
            )
            self.assertTrue(
                {document["id"] for document in TREE_DOCUMENTS}.issubset(
                    {document["id"] for document in catalog["documents"]}
                )
            )
            self.assertIn(
                "repository-tree-webapp-template",
                {document["id"] for document in catalog["documents"]},
            )
            self.assertEqual(manifest["navigation"][1]["title"], "Repository trees")
            self.assertEqual(
                [
                    child["destination"]
                    for child in manifest["navigation"][1]["children"]
                ],
                [
                    "repository-trees/index.md",
                    "repository-trees/skill.md",
                    "repository-trees/policy.md",
                    "repository-trees/webapp.md",
                ],
            )
            self.assertEqual(
                "repository-trees/webapp/template.md",
                manifest["navigation"][2]["destination"],
            )
            self.assertEqual(
                source_catalog,
                (site_root / "docs/publication-catalog.json").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertEqual(
                source_manifest,
                (site_root / "site-manifest.json").read_text(encoding="utf-8"),
            )

            prepare(site_root, output_root)
            self.assertTrue(
                (output_root / "docs/repository-trees/skill.md").is_file()
            )
            self.assertTrue(
                (output_root / "docs/repository-trees/webapp/template.md").is_file()
            )

    def test_preparation_rejects_site_doc_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site_root = root / "site"
            site_root.mkdir()
            self.make_site_source(site_root)
            os.symlink(
                site_root / "docs/index.md",
                site_root / "docs/linked.md",
            )

            with self.assertRaisesRegex(PreparationError, "contains a symlink"):
                prepare(site_root, root / "prepared")


class RepositoryTreeConfigurationTests(unittest.TestCase):
    def test_repository_tree_templates_are_present(self) -> None:
        self.assertTrue((TREE_TEMPLATES / "index.md").is_file())
        for publication in ("skill", "policy", "webapp"):
            template = TREE_TEMPLATES / f"{publication}.md"
            self.assertTrue(template.is_file())
            self.assertIn(
                f"<!-- GENERATED_REPOSITORY_TREE:{publication} -->",
                template.read_text(encoding="utf-8"),
            )
        copyable = TREE_TEMPLATES / "webapp/template.md"
        self.assertTrue(copyable.is_file())
        self.assertIn(
            "<!-- GENERATED_WEBAPP_TEMPLATE_TREE -->",
            copyable.read_text(encoding="utf-8"),
        )

    def test_workflow_prepares_and_generates_trees_before_static_build(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        preparation = workflow.index("- name: Prepare repository-tree publication")
        assembly = workflow.index("- name: Assemble the documentation project")
        generation = workflow.index("- name: Generate repository trees")
        template_generation = workflow.index(
            "- name: Generate Webapp copyable template tree"
        )
        static_build = workflow.index("- name: Build the static site")

        self.assertLess(preparation, assembly)
        self.assertLess(assembly, generation)
        self.assertLess(generation, template_generation)
        self.assertLess(template_generation, static_build)
        self.assertIn(
            "python site-source/scripts/prepare_repository_tree_publication.py",
            workflow,
        )
        self.assertIn(
            "python site-source/scripts/generate_repository_trees.py",
            workflow,
        )
        self.assertIn(
            "python site-source/scripts/generate_webapp_template_tree.py",
            workflow,
        )
        self.assertIn("--publication site=site-publication", workflow)
        self.assertIn("--publication skill=skill-source", workflow)
        self.assertIn("--publication policy=policy-source", workflow)
        self.assertIn("--publication webapp=webapp-source", workflow)
        self.assertIn("build/site/repository-trees/index.html", workflow)
        self.assertIn("build/site/repository-trees/skill/index.html", workflow)
        self.assertIn("build/site/repository-trees/policy/index.html", workflow)
        self.assertIn("build/site/repository-trees/webapp/index.html", workflow)
        self.assertIn(
            "build/site/repository-trees/webapp/template/index.html",
            workflow,
        )

    def test_policy_keeps_inventory_separate_from_publication_boundary(self) -> None:
        raw_policy = POLICY.read_text(encoding="utf-8")
        policy = " ".join(raw_policy.split())

        self.assertIn("## Repository inventory", raw_policy)
        self.assertIn("does not make the file part of the Pages publication", policy)
        self.assertIn("must not copy unlisted file contents", policy)
        self.assertIn("must not follow symlinks or gitlinks", policy)
        self.assertIn("full checked-out commit SHA", policy)


if __name__ == "__main__":
    unittest.main()
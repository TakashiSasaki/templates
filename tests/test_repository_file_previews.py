from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.generate_repository_file_previews import (
    MAX_PREVIEW_BYTES,
    decode_preview_text,
    generate_previews,
)
from scripts.generate_repository_trees import generate


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/site-producer.yml"
CONFIG_TEMPLATE = ROOT / "zensical.template.toml"
POLICY = ROOT / "PUBLISHING.md"
VIEWER_SCRIPT = ROOT / "assets/javascripts/repository-tree-viewer.js"
VIEWER_STYLES = ROOT / "assets/stylesheets/extra.css"


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process.stdout.strip()


class RepositoryFilePreviewTests(unittest.TestCase):
    def make_site(self, root: Path) -> None:
        root.mkdir()
        (root / "site-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "home": {"publication": "skill", "document": "overview"},
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

    def make_publication(self, root: Path, name: str) -> None:
        root.mkdir()
        run_git(root, "init", "--quiet")
        run_git(root, "config", "user.email", "tests@example.invalid")
        run_git(root, "config", "user.name", "Inline preview tests")

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
        (root / "README.md").write_text(
            f"# {name}\n\n<script>alert('escaped')</script>\n",
            encoding="utf-8",
        )
        (root / "notes.txt").write_text("plain text\n", encoding="utf-8")
        (root / "binary.bin").write_bytes(b"\x00\x01\x02")
        (root / "oversized.txt").write_bytes(b"x" * (MAX_PREVIEW_BYTES + 1))
        os.symlink("README.md", root / "readme-link")

        run_git(root, "add", ".")
        run_git(root, "commit", "--quiet", "--message", "fixture")

    def test_generates_sandboxed_escaped_text_previews_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site_root = root / "site"
            output_root = root / "build"
            self.make_site(site_root)
            self.make_templates(output_root)

            publications: dict[str, Path] = {}
            for publication in ("skill", "policy", "webapp"):
                publication_root = root / publication
                self.make_publication(publication_root, publication)
                publications[publication] = publication_root

            generate(
                "TakashiSasaki/templates",
                site_root,
                output_root,
                publications,
            )
            messages = generate_previews(
                "TakashiSasaki/templates",
                site_root,
                output_root,
                publications,
            )

            skill_tree = (
                output_root / "docs/repository-trees/skill.md"
            ).read_text(encoding="utf-8")
            preview_pages = sorted(
                (output_root / "docs/repository-trees/previews/skill").rglob(
                    "*.html"
                )
            )
            preview_source = "\n".join(
                path.read_text(encoding="utf-8") for path in preview_pages
            )

            self.assertEqual(len(messages), 3)
            self.assertEqual(skill_tree.count("repository-file-preview-link"), 3)
            self.assertIn('class="repository-file-viewer"', skill_tree)
            self.assertIn('name="repository-file-preview-skill"', skill_tree)
            self.assertIn('sandbox=""', skill_tree)
            self.assertIn('referrerpolicy="no-referrer"', skill_tree)
            self.assertIn(">preview</a>", skill_tree)
            self.assertIn(">source</a>", skill_tree)
            self.assertIn("/templates/repository-trees/previews/skill/", skill_tree)
            self.assertNotIn("oversized.txt</a></code> <small><a class=", skill_tree)
            self.assertNotIn("binary.bin</a></code> <small><a class=", skill_tree)
            self.assertNotIn("readme-link</a></code> <small><a class=", skill_tree)

            self.assertEqual(len(preview_pages), 3)
            self.assertIn("&lt;script&gt;alert('escaped')&lt;/script&gt;", preview_source)
            self.assertNotIn("<script>alert('escaped')</script>", preview_source)
            self.assertIn("Content-Security-Policy", preview_source)
            self.assertIn("noindex,nofollow", preview_source)

    def test_text_classifier_rejects_binary_non_utf8_controls_and_oversize(self) -> None:
        self.assertEqual(decode_preview_text(b"hello\n"), "hello\n")
        self.assertIsNone(decode_preview_text(b"\x00text"))
        self.assertIsNone(decode_preview_text(b"\xff"))
        self.assertIsNone(decode_preview_text(b"escape\x1bsequence"))
        self.assertIsNone(decode_preview_text("left\u202eright".encode("utf-8")))
        self.assertIsNone(decode_preview_text("left\u2066right".encode("utf-8")))
        self.assertIsNone(decode_preview_text(b"x" * (MAX_PREVIEW_BYTES + 1)))


class RepositoryFilePreviewConfigurationTests(unittest.TestCase):
    def test_workflow_generates_previews_between_trees_and_static_build(self):
        text=(Path(__file__).resolve().parents[1]/'site_renderer/render.py').read_text()
        self.assertLess(text.index('trees.render_tree('),text.index('previews.write_preview_pages('))
        self.assertLess(text.index('previews.write_preview_pages('),text.index("'zensical'))"))
        self.assertIn("source_previews=[record(PreviewRecord,r) for r in model['previews']]",text)
        self.assertNotIn('collect_previews(',text)

    def test_viewer_assets_and_policy_define_the_security_boundary(self) -> None:
        config = CONFIG_TEMPLATE.read_text(encoding="utf-8")
        policy = " ".join(POLICY.read_text(encoding="utf-8").split())
        script = VIEWER_SCRIPT.read_text(encoding="utf-8")
        styles = VIEWER_STYLES.read_text(encoding="utf-8")

        self.assertIn('"javascripts/repository-tree-viewer.js"', config)
        self.assertIn("sandboxed inline frame", policy)
        self.assertIn("UTF-8 text", policy)
        self.assertIn("256 KiB", policy)
        self.assertIn("Git blob objects", policy)
        self.assertIn("addEventListener", script)
        self.assertNotIn("innerHTML", script)
        self.assertIn(".repository-file-viewer", styles)


if __name__ == "__main__":
    unittest.main()

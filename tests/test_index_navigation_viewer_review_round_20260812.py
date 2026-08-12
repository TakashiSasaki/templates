from __future__ import annotations

import html
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.generate_index_navigation import PROVIDER_ORDER, generate_graph
from scripts import generate_index_navigation_viewer as viewer


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process.stdout.strip()


def make_provider(root: Path, provider: str) -> None:
    root.mkdir()
    run_git(root, "init", "--quiet")
    run_git(root, "config", "user.email", "tests@example.invalid")
    run_git(root, "config", "user.name", "Viewer review round tests")
    (root / "docs").mkdir()
    (root / "docs/index.md").write_text(
        f"# {provider.title()} docs\n\n"
        "## Guides\n\n"
        "* [Overview](overview.md) - Open the overview.\n",
        encoding="utf-8",
    )
    (root / "docs/overview.md").write_text("# Overview\n", encoding="utf-8")
    (root / "docs/publication-catalog.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "documents": [
                    {
                        "id": "overview",
                        "source": "docs/overview.md",
                        "optional": False,
                        "home": True,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    run_git(root, "add", ".")
    run_git(root, "commit", "--quiet", "--message", "fixture")


def make_fixture(root: Path):
    providers = {}
    for provider in PROVIDER_ORDER:
        provider_root = root / provider
        make_provider(provider_root, provider)
        providers[provider] = provider_root

    site_root = root / "site-root"
    site_root.mkdir()
    navigation = [
        {
            "title": provider.title(),
            "publication": provider,
            "document": "overview",
            "destination": f"{provider}/index.md",
        }
        for provider in PROVIDER_ORDER
    ]
    (site_root / "site-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "home": {"publication": "site", "document": "portal-home"},
                "navigation": navigation,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = root / "output"
    output.mkdir()
    return providers, site_root, output


def rewrite_skill_index(providers: dict[str, Path], content: str) -> None:
    skill = providers["skill"]
    (skill / "docs/index.md").write_text(content, encoding="utf-8")
    run_git(skill, "add", "docs/index.md")
    run_git(skill, "commit", "--quiet", "--message", "review fixture")


class CurrentIndexNavigationViewerReviewTests(unittest.TestCase):
    def test_producer_normalized_escaped_literal_heading_is_renderable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output = make_fixture(root)
            rewrite_skill_index(
                providers,
                "# Skill docs\n\n"
                r"## \[Guides\]\(v2\)"
                "\n\n"
                "* [Overview](overview.md) - Open the overview.\n",
            )
            graph = generate_graph("TakashiSasaki/templates", providers)
            skill = graph["providers"][0]
            self.assertEqual(skill["indexes"][0]["sections"][0]["title"], "[Guides](v2)")

            viewer.generate_viewer(
                "TakashiSasaki/templates", graph, site_root, output, providers
            )

            page = (output / "guided/skill/index.html").read_text(encoding="utf-8")
            self.assertIn('<h2 id="guidesv2">[Guides](v2)</h2>', page)

    def test_index_blob_id_must_match_the_locked_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output = make_fixture(root)
            graph = generate_graph("TakashiSasaki/templates", providers)
            graph["providers"][0]["indexes"][0]["object_id"] = "0" * 40

            with self.assertRaisesRegex(
                viewer.IndexNavigationViewerError,
                "index object does not match locked revision",
            ):
                viewer.generate_viewer(
                    "TakashiSasaki/templates", graph, site_root, output, providers
                )
            self.assertFalse((output / "guided").exists())

    def test_repository_root_directory_sentinel_is_renderable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output = make_fixture(root)
            rewrite_skill_index(
                providers,
                "# Skill docs\n\n"
                "## Guides\n\n"
                "* [Repository root](../) - Browse the repository root.\n"
                "* [Root fragment](../#usage) - Preserve a root fragment.\n"
                "* [Overview](overview.md) - Open the overview.\n",
            )
            graph = generate_graph("TakashiSasaki/templates", providers)
            skill = graph["providers"][0]
            root_edges = [
                edge
                for edge in skill["edges"]
                if edge["kind"] == "directory" and edge["target"] == "."
            ]
            self.assertEqual(len(root_edges), 2)

            viewer.generate_viewer(
                "TakashiSasaki/templates", graph, site_root, output, providers
            )

            page = (output / "guided/skill/index.html").read_text(encoding="utf-8")
            self.assertIn('href="/files/skill/"', page)
            revision = skill["revision"]
            self.assertIn(
                f'href="https://github.com/TakashiSasaki/templates/tree/{revision}#usage"',
                page,
            )
            self.assertNotIn(f"/tree/{revision}/.#usage", page)

    def test_producer_normalized_internationalized_external_host_is_renderable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output = make_fixture(root)
            rewrite_skill_index(
                providers,
                "# Skill docs\n\n"
                "## Guides\n\n"
                "* [Internationalized specification](https://例え.テスト/spec) - Open the specification.\n"
                "* [Overview](overview.md) - Open the overview.\n",
            )
            graph = generate_graph("TakashiSasaki/templates", providers)
            skill = graph["providers"][0]
            external = next(edge for edge in skill["edges"] if edge["kind"] == "external")
            self.assertIn("%", external["target"])

            viewer.generate_viewer(
                "TakashiSasaki/templates", graph, site_root, output, providers
            )

            page = (output / "guided/skill/index.html").read_text(encoding="utf-8")
            self.assertIn(
                f'href="{html.escape(external["target"], quote=True)}"',
                page,
            )

    def test_heading_anchor_collapses_repeated_whitespace(self) -> None:
        self.assertEqual(viewer.heading_anchor("Foo  Bar"), "foo-bar")


if __name__ == "__main__":
    unittest.main()

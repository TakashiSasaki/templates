from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.generate_index_navigation import PROVIDER_ORDER, generate_graph
from scripts.generate_index_navigation_viewer import (
    IndexNavigationViewerError,
    generate_viewer,
    index_page_path,
    load_graph,
)
from scripts.generate_repository_browser import viewer_relative_url


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process.stdout.strip()


class IndexNavigationViewerTests(unittest.TestCase):
    def make_provider(self, root: Path, provider: str) -> None:
        root.mkdir()
        run_git(root, "init", "--quiet")
        run_git(root, "config", "user.email", "tests@example.invalid")
        run_git(root, "config", "user.name", "Index navigation viewer tests")
        (root / "docs/architecture").mkdir(parents=True)
        (root / "docs/index.md").write_text(
            f"# {provider.title()} documentation\n\n"
            "## Guided links\n\n"
            "* [Jump to this section](#guided-links) - Exercise a same-index fragment.\n"
            "* [Architecture](architecture/#details) - Follow the nested index and fragment.\n"
            "* [Overview](overview.md#scope) - Open the cataloged document.\n"
            "* [<script>notes</script>](../notes.txt#L1) - Read <b>escaped</b> source metadata.\n"
            "* [Specification](https://example.com/spec#caf%C3%A9) - Open the external specification.\n",
            encoding="utf-8",
        )
        (root / "docs/architecture/index.md").write_text(
            "# Architecture\n\n"
            "## Details\n\n"
            "* [Boundary](boundary.md) - Read an uncataloged architecture file.\n",
            encoding="utf-8",
        )
        (root / "docs/architecture/boundary.md").write_text(
            "# Boundary\n", encoding="utf-8"
        )
        (root / "docs/overview.md").write_text("# Overview\n\n## Scope\n", encoding="utf-8")
        (root / "notes.txt").write_text("notes\n", encoding="utf-8")
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
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        run_git(root, "add", ".")
        run_git(root, "commit", "--quiet", "--message", "fixture")

    def make_site_root(self, root: Path) -> None:
        root.mkdir()
        navigation = []
        for provider in PROVIDER_ORDER:
            navigation.append(
                {
                    "title": provider.title(),
                    "publication": provider,
                    "document": "overview",
                    "destination": f"{provider}/index.md",
                }
            )
        (root / "site-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "home": {"publication": "site", "document": "portal-home"},
                    "navigation": navigation,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def make_fixture(self, root: Path):
        providers = {}
        for provider in PROVIDER_ORDER:
            provider_root = root / provider
            self.make_provider(provider_root, provider)
            providers[provider] = provider_root
        site_root = root / "site-root"
        self.make_site_root(site_root)
        output = root / "output"
        output.mkdir()
        graph = generate_graph("TakashiSasaki/templates", providers)
        return providers, site_root, output, graph

    def test_generates_landing_provider_and_nested_index_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output, graph = self.make_fixture(root)
            messages = generate_viewer(
                "TakashiSasaki/templates", graph, site_root, output, providers
            )

            self.assertEqual(len(messages), 3)
            self.assertTrue((output / "guided/index.html").is_file())
            self.assertTrue((output / "guided/graph.json").is_file())
            self.assertTrue((output / "guided/skill/index.html").is_file())
            self.assertTrue(
                (output / "guided/skill/docs/architecture/index.html").is_file()
            )
            self.assertEqual(
                index_page_path("skill", "docs/index.md"),
                Path("guided/skill/index.html"),
            )

            page = (output / "guided/skill/index.html").read_text(encoding="utf-8")
            revision = graph["providers"][0]["revision"]
            self.assertIn(revision, page)
            self.assertIn('id="skill-documentation"', page)
            self.assertIn('id="guided-links"', page)
            self.assertIn('href="#guided-links"', page)
            self.assertIn('href="/guided/skill/docs/architecture/#details"', page)
            self.assertIn('href="/skill/#scope"', page)
            notes_relative = viewer_relative_url("skill", revision, b"notes.txt")
            self.assertIn(f'href="/files/skill/{notes_relative}#L1"', page)
            self.assertIn('href="https://example.com/spec#caf%C3%A9"', page)
            self.assertNotIn("caf%25C3%25A9", page)
            self.assertIn('target="_blank" rel="noopener"', page)
            self.assertIn("&lt;script&gt;notes&lt;/script&gt;", page)
            self.assertIn("Read &lt;b&gt;escaped&lt;/b&gt; source metadata.", page)
            self.assertNotIn("<script>notes</script>", page)
            self.assertIn("Content-Security-Policy", page)
            self.assertIn("index line", page)
            self.assertIn("immutable source", page)

            nested = (
                output / "guided/skill/docs/architecture/index.html"
            ).read_text(encoding="utf-8")
            self.assertIn('id="details"', nested)

            saved_graph = json.loads(
                (output / "guided/graph.json").read_text(encoding="utf-8")
            )
            self.assertEqual(saved_graph, graph)
            external = next(
                edge
                for edge in saved_graph["providers"][0]["edges"]
                if edge["label"] == "Specification"
            )
            self.assertEqual(external["target"], "https://example.com/spec")
            self.assertEqual(external["fragment"], "café")

    def test_duplicate_section_names_in_tampered_graph_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output, graph = self.make_fixture(root)
            graph["providers"][0]["indexes"][0]["sections"] = [
                "Guided links",
                "Guided links",
            ]
            with self.assertRaisesRegex(
                IndexNavigationViewerError, "duplicate section headings"
            ):
                generate_viewer(
                    "TakashiSasaki/templates", graph, site_root, output, providers
                )
            self.assertFalse((output / "guided").exists())

    def test_revision_mismatch_fails_before_creating_guided_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output, graph = self.make_fixture(root)
            skill = providers["skill"]
            (skill / "new.txt").write_text("new\n", encoding="utf-8")
            run_git(skill, "add", "new.txt")
            run_git(skill, "commit", "--quiet", "--message", "advance revision")

            with self.assertRaisesRegex(IndexNavigationViewerError, "does not match checkout"):
                generate_viewer(
                    "TakashiSasaki/templates", graph, site_root, output, providers
                )
            self.assertFalse((output / "guided").exists())

    def test_existing_guided_destination_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output, graph = self.make_fixture(root)
            guided = output / "guided"
            guided.mkdir()
            sentinel = guided / "keep.txt"
            sentinel.write_text("keep\n", encoding="utf-8")

            with self.assertRaisesRegex(IndexNavigationViewerError, "already exists"):
                generate_viewer(
                    "TakashiSasaki/templates", graph, site_root, output, providers
                )
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")

    def test_load_graph_rejects_wrong_schema_and_provider_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            graph_path = root / "graph.json"
            graph_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "repository": "TakashiSasaki/templates",
                        "providers": [],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(IndexNavigationViewerError, "schema_version 1"):
                load_graph(graph_path)

            graph_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repository": "TakashiSasaki/templates",
                        "providers": [
                            {"name": "policy"},
                            {"name": "skill"},
                            {"name": "webapp"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(IndexNavigationViewerError, "ordered exactly"):
                load_graph(graph_path)


if __name__ == "__main__":
    unittest.main()

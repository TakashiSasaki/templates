from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.generate_index_navigation import PROVIDER_ORDER, generate_graph
from scripts import generate_index_navigation_viewer as viewer
from scripts.generate_repository_trees import RepositoryTreeError


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
    run_git(root, "config", "user.name", "Latest viewer review tests")
    (root / "docs").mkdir()
    (root / "docs/index.md").write_text(
        f"# {provider.title()} docs\n\n"
        "## Guides\n\n"
        "* [Examples](examples/#usage) - Preserve a directory fragment.\n\n"
        "### Advanced\n\n"
        "* [Overview](overview.md) - Preserve nested heading depth.\n",
        encoding="utf-8",
    )
    (root / "docs/examples").mkdir()
    (root / "docs/examples/README.md").write_text(
        "# Examples\n\n## Usage\n",
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
    return providers, site_root, output, generate_graph(
        "TakashiSasaki/templates", providers
    )


class LatestIndexNavigationViewerReviewTests(unittest.TestCase):
    def test_root_level_index_gets_reserved_guided_route(self) -> None:
        self.assertEqual(
            viewer.index_page_path("skill", "docs/index.md"),
            Path("guided/skill/index.html"),
        )
        self.assertEqual(
            viewer.index_page_path("skill", "index.md"),
            Path("guided/_repository-root/skill/index.html"),
        )
        self.assertEqual(
            viewer.index_page_url("skill", "index.md"),
            "/guided/_repository-root/skill/",
        )
        self.assertNotEqual(
            viewer.index_page_path("skill", "index.md"),
            viewer.index_page_path("skill", "repository-root/index.md"),
        )

    def test_directory_fragment_uses_immutable_tree_url(self) -> None:
        href, kind, external = viewer.edge_href(
            "skill",
            "a" * 40,
            {"kind": "directory", "target": "docs/examples", "fragment": "usage"},
            {},
            "TakashiSasaki/templates",
        )
        self.assertEqual(
            href,
            "https://github.com/TakashiSasaki/templates/tree/"
            + ("a" * 40)
            + "/docs/examples#usage",
        )
        self.assertEqual(kind, "immutable directory")
        self.assertTrue(external)

    def test_provider_heading_levels_are_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output, graph = make_fixture(root)
            viewer.generate_viewer(
                "TakashiSasaki/templates", graph, site_root, output, providers
            )
            page = (output / "guided/skill/index.html").read_text(encoding="utf-8")
            self.assertIn('<h2 id="guides">Guides</h2>', page)
            self.assertIn('<h3 id="advanced">Advanced</h3>', page)

    def test_inline_markdown_heading_is_rejected_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output, graph = make_fixture(root)
            graph["providers"][0]["indexes"][0]["sections"][0] = {
                "title": "[Guides](guide.md)",
                "level": 2,
            }
            with self.assertRaisesRegex(
                viewer.IndexNavigationViewerError,
                "plain heading text",
            ):
                viewer.generate_viewer(
                    "TakashiSasaki/templates", graph, site_root, output, providers
                )
            self.assertFalse((output / "guided").exists())

    def test_render_failures_happen_before_guided_output_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output, graph = make_fixture(root)
            graph["providers"][0]["indexes"][0]["title"] = "!!!"
            with self.assertRaisesRegex(
                viewer.IndexNavigationViewerError,
                "heading cannot produce a stable anchor",
            ):
                viewer.generate_viewer(
                    "TakashiSasaki/templates", graph, site_root, output, providers
                )
            self.assertFalse((output / "guided").exists())

    def test_output_file_directory_collisions_are_rejected_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output, graph = make_fixture(root)
            skill = graph["providers"][0]
            skill["indexes"].extend(
                [
                    {
                        "path": "docs/a/index.md",
                        "title": "A",
                        "sections": [],
                        "depth": 1,
                        "object_id": "1" * 40,
                    },
                    {
                        "path": "docs/a/index.html/index.md",
                        "title": "Nested A",
                        "sections": [],
                        "depth": 2,
                        "object_id": "2" * 40,
                    },
                ]
            )
            with self.assertRaisesRegex(
                viewer.IndexNavigationViewerError,
                "file/directory collision",
            ):
                viewer.generate_viewer(
                    "TakashiSasaki/templates", graph, site_root, output, providers
                )
            self.assertFalse((output / "guided").exists())

    def test_tampered_index_traversal_is_rejected_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            providers, site_root, output, graph = make_fixture(root)
            graph["providers"][0]["indexes"][0]["path"] = "../../../victim/index.md"
            with self.assertRaisesRegex(
                viewer.IndexNavigationViewerError,
                "safe repository-relative path",
            ):
                viewer.generate_viewer(
                    "TakashiSasaki/templates", graph, site_root, output, providers
                )
            self.assertFalse((output / "guided").exists())

    def test_cli_formats_repository_tree_errors_as_parser_errors(self) -> None:
        argv = [
            "generate_index_navigation_viewer.py",
            "--repository", "TakashiSasaki/templates",
            "--graph", "graph.json",
            "--site-root", "site",
            "--output-root", "out",
            "--provider", "skill=skill",
            "--provider", "policy=policy",
            "--provider", "webapp=webapp",
        ]
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", argv), mock.patch.object(
            viewer, "load_graph", return_value={"repository": "TakashiSasaki/templates"}
        ), mock.patch.object(
            viewer,
            "generate_viewer",
            side_effect=RepositoryTreeError("repository inspection failed"),
        ), mock.patch.object(sys, "stderr", stderr):
            with self.assertRaises(SystemExit) as raised:
                viewer.main()
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("repository inspection failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

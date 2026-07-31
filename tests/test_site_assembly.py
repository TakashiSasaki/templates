#!/usr/bin/env python3
"""Regression tests for the documentation-site manifest and assembly."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from typing import Any

SITE_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = SITE_ROOT / "site-manifest.json"
ASSEMBLER_PATH = SITE_ROOT / "scripts" / "assemble_docs.py"

EXPECTED_NAVIGATION = [
    ("Overview", "README.md"),
    (
        "Getting started",
        [
            ("Skill contract", "SKILL.md"),
            ("Skill profiles", "docs/skill-profiles.md"),
            ("Profile contract map", "docs/profile-contract-map.md"),
        ],
    ),
    (
        "Core contracts",
        [
            ("Runtime decision record", "RUNTIME.md"),
            ("Interface routing", "INTERFACES.md"),
        ],
    ),
    (
        "Caller interfaces",
        [
            ("Packaged CLI interface", "CLI_INTERFACE.md"),
            ("MCP interface", "MCP_INTERFACE.md"),
            ("Human Web interface", "WEB_INTERFACE.md"),
        ],
    ),
    (
        "Design guidance",
        [
            ("Architecture", "docs/architecture.md"),
            ("Runtime selection", "docs/runtime-selection.md"),
            ("MCP transports", "docs/mcp-transports.md"),
        ],
    ),
]


def flatten_pages(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for node in nodes:
        if "children" in node:
            pages.extend(flatten_pages(node["children"]))
        else:
            pages.append(node)
    return pages


def navigation_shape(nodes: list[dict[str, Any]]) -> list[tuple[str, object]]:
    shape: list[tuple[str, object]] = []
    for node in nodes:
        if "children" in node:
            shape.append((node["title"], navigation_shape(node["children"])))
        else:
            shape.append((node["title"], node["source"]))
    return shape


def toml_nav_shape(nodes: list[object]) -> list[tuple[str, object]]:
    shape: list[tuple[str, object]] = []
    for node in nodes:
        if not isinstance(node, dict) or len(node) != 1:
            raise AssertionError(f"unexpected TOML navigation node: {node!r}")
        title, value = next(iter(node.items()))
        if isinstance(value, list):
            shape.append((title, toml_nav_shape(value)))
        else:
            shape.append((title, value))
    return shape


class SiteAssemblyTests(unittest.TestCase):
    def load_navigation(self) -> list[dict[str, Any]]:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        navigation = manifest.get("navigation")
        self.assertIsInstance(navigation, list)
        return navigation

    def run_assembler(
        self,
        source_root: Path,
        output_root: Path,
        site_root: Path = SITE_ROOT,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(ASSEMBLER_PATH),
                "--source-root",
                str(source_root),
                "--site-root",
                str(site_root),
                "--output-root",
                str(output_root),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def create_canonical_source(
        self,
        root: Path,
        pages: list[dict[str, Any]],
        *,
        omit: set[str] | None = None,
    ) -> Path:
        source_root = root / "canonical-source"
        source_root.mkdir()
        omitted = omit or set()
        for page in pages:
            if page["source"] in omitted:
                continue
            source = source_root / page["source"]
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(f"# {page['title']}\n", encoding="utf-8")
        return source_root

    def create_site_root(self, root: Path, manifest: dict[str, Any]) -> Path:
        site_root = root / "site-source"
        site_root.mkdir(parents=True)
        (site_root / "site-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        shutil.copy2(SITE_ROOT / "zensical.template.toml", site_root)
        return site_root

    def test_manifest_has_profile_centered_hierarchy_and_unique_values(self) -> None:
        navigation = self.load_navigation()
        pages = flatten_pages(navigation)

        self.assertEqual(navigation_shape(navigation), EXPECTED_NAVIGATION)
        self.assertEqual(pages[0]["destination"], "index.md")

        for field in ("source", "destination", "title"):
            values = [page[field] for page in pages]
            self.assertEqual(
                len(values), len(set(values)), f"page {field} values must be unique"
            )

        def collect_titles(nodes: list[dict[str, Any]]) -> list[str]:
            titles: list[str] = []
            for node in nodes:
                titles.append(node["title"])
                if "children" in node:
                    titles.extend(collect_titles(node["children"]))
            return titles

        titles = collect_titles(navigation)
        self.assertEqual(len(titles), len(set(titles)), "all nav titles must be unique")

    def test_assembly_copies_pages_and_renders_nested_navigation(self) -> None:
        navigation = self.load_navigation()
        pages = flatten_pages(navigation)

        with tempfile.TemporaryDirectory(prefix="site-assembly-test-") as directory:
            root = Path(directory)
            source_root = self.create_canonical_source(root, pages)
            output_root = root / "build"

            result = self.run_assembler(source_root, output_root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"assembled {len(pages)} page(s)", result.stdout)

            for page in pages:
                self.assertTrue(
                    (output_root / "docs" / page["destination"]).is_file(),
                    f"missing assembled page: {page['destination']}",
                )

            config = tomllib.loads(
                (output_root / "zensical.toml").read_text(encoding="utf-8")
            )
            generated_shape = toml_nav_shape(config["project"]["nav"])
            expected_destinations = [
                ("Overview", "index.md"),
                (
                    "Getting started",
                    [
                        ("Skill contract", "SKILL.md"),
                        ("Skill profiles", "docs/skill-profiles.md"),
                        ("Profile contract map", "docs/profile-contract-map.md"),
                    ],
                ),
                (
                    "Core contracts",
                    [
                        ("Runtime decision record", "RUNTIME.md"),
                        ("Interface routing", "INTERFACES.md"),
                    ],
                ),
                (
                    "Caller interfaces",
                    [
                        ("Packaged CLI interface", "CLI_INTERFACE.md"),
                        ("MCP interface", "MCP_INTERFACE.md"),
                        ("Human Web interface", "WEB_INTERFACE.md"),
                    ],
                ),
                (
                    "Design guidance",
                    [
                        ("Architecture", "docs/architecture.md"),
                        ("Runtime selection", "docs/runtime-selection.md"),
                        ("MCP transports", "docs/mcp-transports.md"),
                    ],
                ),
            ]
            self.assertEqual(generated_shape, expected_destinations)

    def test_missing_optional_page_is_removed_from_its_section(self) -> None:
        navigation = self.load_navigation()
        pages = flatten_pages(navigation)
        omitted = {"docs/mcp-transports.md"}

        with tempfile.TemporaryDirectory(prefix="site-optional-test-") as directory:
            root = Path(directory)
            source_root = self.create_canonical_source(root, pages, omit=omitted)
            output_root = root / "build"

            result = self.run_assembler(source_root, output_root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "optional pages skipped: docs/mcp-transports.md", result.stdout
            )
            config = tomllib.loads(
                (output_root / "zensical.toml").read_text(encoding="utf-8")
            )
            generated_shape = toml_nav_shape(config["project"]["nav"])
            design_children = dict(generated_shape)["Design guidance"]
            self.assertNotIn(("MCP transports", "docs/mcp-transports.md"), design_children)

    def test_section_with_only_missing_optional_pages_is_omitted(self) -> None:
        manifest = {
            "navigation": [
                {
                    "title": "Overview",
                    "source": "README.md",
                    "destination": "index.md",
                },
                {
                    "title": "Optional section",
                    "children": [
                        {
                            "title": "Optional page",
                            "source": "optional.md",
                            "destination": "optional.md",
                            "optional": True,
                        }
                    ],
                },
            ]
        }
        with tempfile.TemporaryDirectory(prefix="site-empty-optional-test-") as directory:
            root = Path(directory)
            source_root = root / "canonical-source"
            source_root.mkdir()
            (source_root / "README.md").write_text("# Overview\n", encoding="utf-8")
            site_root = self.create_site_root(root, manifest)
            output_root = root / "build"
            result = self.run_assembler(source_root, output_root, site_root)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = tomllib.loads(
                (output_root / "zensical.toml").read_text(encoding="utf-8")
            )
            self.assertEqual(
                toml_nav_shape(config["project"]["nav"]),
                [("Overview", "index.md")],
            )

    def test_rejects_empty_section_and_mixed_page_section_nodes(self) -> None:
        invalid_nodes = (
            {"title": "Empty", "children": []},
            {
                "title": "Mixed",
                "source": "README.md",
                "destination": "index.md",
                "children": [
                    {
                        "title": "Child",
                        "source": "SKILL.md",
                        "destination": "SKILL.md",
                    }
                ],
            },
            {
                "title": "Unknown",
                "source": "README.md",
                "destination": "index.md",
                "unexpected": True,
            },
        )
        with tempfile.TemporaryDirectory(prefix="site-schema-test-") as directory:
            root = Path(directory)
            source_root = root / "canonical-source"
            source_root.mkdir()
            for index, node in enumerate(invalid_nodes):
                site_root = self.create_site_root(
                    root / f"case-{index}", {"navigation": [node]}
                )
                result = self.run_assembler(
                    source_root, root / f"build-{index}", site_root
                )
                self.assertNotEqual(result.returncode, 0)

    def test_rejects_duplicate_destination_across_sections(self) -> None:
        manifest = {
            "navigation": [
                {
                    "title": "First",
                    "children": [
                        {
                            "title": "Page A",
                            "source": "a.md",
                            "destination": "same.md",
                        }
                    ],
                },
                {
                    "title": "Second",
                    "children": [
                        {
                            "title": "Page B",
                            "source": "b.md",
                            "destination": "same.md",
                        }
                    ],
                },
            ]
        }
        with tempfile.TemporaryDirectory(prefix="site-duplicate-test-") as directory:
            root = Path(directory)
            source_root = root / "canonical-source"
            source_root.mkdir()
            site_root = self.create_site_root(root, manifest)
            result = self.run_assembler(source_root, root / "build", site_root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Duplicate destination: same.md", result.stderr)


if __name__ == "__main__":
    unittest.main()

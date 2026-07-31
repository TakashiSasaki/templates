#!/usr/bin/env python3
"""Regression tests for publication-catalog-backed site assembly."""

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

CATALOG_DOCUMENTS = [
    {"id": "overview", "source": "README.md", "optional": False, "home": True},
    {"id": "skill-contract", "source": "SKILL.md", "optional": False, "home": False},
    {"id": "skill-profiles", "source": "docs/skill-profiles.md", "optional": False, "home": False},
    {"id": "profile-contract-map", "source": "docs/profile-contract-map.md", "optional": False, "home": False},
    {"id": "runtime-decision-record", "source": "RUNTIME.md", "optional": False, "home": False},
    {"id": "interface-routing", "source": "INTERFACES.md", "optional": False, "home": False},
    {"id": "packaged-cli-interface", "source": "CLI_INTERFACE.md", "optional": False, "home": False},
    {"id": "mcp-interface", "source": "MCP_INTERFACE.md", "optional": False, "home": False},
    {"id": "human-web-interface", "source": "WEB_INTERFACE.md", "optional": False, "home": False},
    {"id": "architecture", "source": "docs/architecture.md", "optional": False, "home": False},
    {"id": "runtime-selection", "source": "docs/runtime-selection.md", "optional": False, "home": False},
    {"id": "mcp-transports", "source": "docs/mcp-transports.md", "optional": True, "home": False},
]

EXPECTED_NAVIGATION = [
    ("Overview", "overview"),
    (
        "Getting started",
        [
            ("Skill contract", "skill-contract"),
            ("Skill profiles", "skill-profiles"),
            ("Profile contract map", "profile-contract-map"),
        ],
    ),
    (
        "Core contracts",
        [
            ("Runtime decision record", "runtime-decision-record"),
            ("Interface routing", "interface-routing"),
        ],
    ),
    (
        "Caller interfaces",
        [
            ("Packaged CLI interface", "packaged-cli-interface"),
            ("MCP interface", "mcp-interface"),
            ("Human Web interface", "human-web-interface"),
        ],
    ),
    (
        "Design guidance",
        [
            ("Architecture", "architecture"),
            ("Runtime selection", "runtime-selection"),
            ("MCP transports", "mcp-transports"),
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
            shape.append((node["title"], node["document"]))
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
    def load_manifest(self) -> dict[str, Any]:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

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

    def write_catalog(
        self,
        source_root: Path,
        documents: list[dict[str, Any]] = CATALOG_DOCUMENTS,
    ) -> None:
        catalog_path = source_root / "docs" / "publication-catalog.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps({"schema_version": 1, "documents": documents}),
            encoding="utf-8",
        )

    def create_canonical_source(
        self,
        root: Path,
        *,
        documents: list[dict[str, Any]] = CATALOG_DOCUMENTS,
        omit_ids: set[str] | None = None,
    ) -> Path:
        source_root = root / "canonical-source"
        source_root.mkdir(parents=True)
        self.write_catalog(source_root, documents)
        omitted = omit_ids or set()
        for document in documents:
            if document["id"] in omitted:
                continue
            source = source_root / document["source"]
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(f"# {document['id']}\n", encoding="utf-8")
        return source_root

    def create_site_root(self, root: Path, manifest: dict[str, Any]) -> Path:
        site_root = root / "site-source"
        site_root.mkdir(parents=True)
        (site_root / "site-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        shutil.copy2(SITE_ROOT / "zensical.template.toml", site_root)
        return site_root

    def test_manifest_uses_catalog_ids_and_covers_every_document_once(self) -> None:
        manifest = self.load_manifest()
        navigation = manifest["navigation"]
        pages = flatten_pages(navigation)

        self.assertEqual(navigation_shape(navigation), EXPECTED_NAVIGATION)
        self.assertEqual(pages[0]["document"], "overview")
        self.assertEqual(pages[0]["destination"], "index.md")
        self.assertNotIn("source", pages[0])
        self.assertNotIn("optional", pages[0])

        page_ids = [page["document"] for page in pages]
        catalog_ids = [document["id"] for document in CATALOG_DOCUMENTS]
        self.assertEqual(set(page_ids), set(catalog_ids))
        self.assertEqual(len(page_ids), len(set(page_ids)))

    def test_assembly_resolves_sources_and_optionality_from_catalog(self) -> None:
        manifest = self.load_manifest()
        pages = flatten_pages(manifest["navigation"])
        documents = {document["id"]: document for document in CATALOG_DOCUMENTS}

        with tempfile.TemporaryDirectory(prefix="site-assembly-test-") as directory:
            root = Path(directory)
            source_root = self.create_canonical_source(root)
            output_root = root / "build"

            result = self.run_assembler(source_root, output_root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"assembled {len(pages)} page(s)", result.stdout)
            self.assertIn(f"catalog documents: {len(CATALOG_DOCUMENTS)}", result.stdout)

            for page in pages:
                destination = output_root / "docs" / page["destination"]
                self.assertTrue(destination.is_file(), page["destination"])
                self.assertIn(
                    documents[page["document"]]["id"],
                    destination.read_text(encoding="utf-8"),
                )

            config = tomllib.loads(
                (output_root / "zensical.toml").read_text(encoding="utf-8")
            )
            generated = toml_nav_shape(config["project"]["nav"])
            self.assertEqual(
                generated,
                [
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
                ],
            )

    def test_catalog_source_rename_requires_no_site_manifest_source_change(self) -> None:
        documents = [dict(document) for document in CATALOG_DOCUMENTS]
        documents[0]["source"] = "HOME.md"
        with tempfile.TemporaryDirectory(prefix="site-source-authority-test-") as directory:
            root = Path(directory)
            source_root = self.create_canonical_source(root, documents=documents)
            output_root = root / "build"
            result = self.run_assembler(source_root, output_root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (output_root / "docs" / "index.md").read_text(encoding="utf-8"),
                "# overview\n",
            )

    def test_missing_optional_catalog_source_is_removed_from_navigation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="site-optional-test-") as directory:
            root = Path(directory)
            source_root = self.create_canonical_source(
                root, omit_ids={"mcp-transports"}
            )
            output_root = root / "build"
            result = self.run_assembler(source_root, output_root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "optional documents skipped: mcp-transports", result.stdout
            )
            config = tomllib.loads(
                (output_root / "zensical.toml").read_text(encoding="utf-8")
            )
            design_children = dict(toml_nav_shape(config["project"]["nav"]))[
                "Design guidance"
            ]
            self.assertNotIn(("MCP transports", "docs/mcp-transports.md"), design_children)

    def test_rejects_catalog_manifest_coverage_mismatch(self) -> None:
        manifest = self.load_manifest()
        manifest["navigation"][-1]["children"].pop()
        with tempfile.TemporaryDirectory(prefix="site-coverage-test-") as directory:
            root = Path(directory)
            source_root = self.create_canonical_source(root)
            site_root = self.create_site_root(root, manifest)
            result = self.run_assembler(source_root, root / "build", site_root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "site manifest does not cover publication document IDs: mcp-transports",
                result.stderr,
            )

    def test_rejects_unknown_document_id_and_legacy_source_fields(self) -> None:
        invalid_pages = [
            {"title": "Overview", "document": "unknown", "destination": "index.md"},
            {
                "title": "Overview",
                "document": "overview",
                "source": "README.md",
                "destination": "index.md",
            },
            {
                "title": "Overview",
                "document": "overview",
                "destination": "index.md",
                "optional": False,
            },
        ]
        with tempfile.TemporaryDirectory(prefix="site-page-schema-test-") as directory:
            root = Path(directory)
            source_root = self.create_canonical_source(root)
            for index, page in enumerate(invalid_pages):
                site_root = self.create_site_root(
                    root / f"case-{index}", {"navigation": [page]}
                )
                result = self.run_assembler(
                    source_root, root / f"build-{index}", site_root
                )
                self.assertNotEqual(result.returncode, 0)

    def test_rejects_duplicate_document_and_destination(self) -> None:
        cases = [
            {
                "navigation": [
                    {"title": "A", "document": "overview", "destination": "index.md"},
                    {"title": "B", "document": "overview", "destination": "b.md"},
                ]
            },
            {
                "navigation": [
                    {"title": "A", "document": "overview", "destination": "index.md"},
                    {
                        "title": "B",
                        "document": "skill-contract",
                        "destination": "index.md",
                    },
                ]
            },
        ]
        with tempfile.TemporaryDirectory(prefix="site-duplicate-test-") as directory:
            root = Path(directory)
            source_root = self.create_canonical_source(root)
            for index, manifest in enumerate(cases):
                site_root = self.create_site_root(root / f"case-{index}", manifest)
                result = self.run_assembler(
                    source_root, root / f"build-{index}", site_root
                )
                self.assertNotEqual(result.returncode, 0)

    def test_rejects_non_home_first_page(self) -> None:
        manifest = self.load_manifest()
        overview = manifest["navigation"].pop(0)
        manifest["navigation"].insert(1, overview)
        with tempfile.TemporaryDirectory(prefix="site-home-test-") as directory:
            root = Path(directory)
            source_root = self.create_canonical_source(root)
            site_root = self.create_site_root(root, manifest)
            result = self.run_assembler(source_root, root / "build", site_root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("first navigation entry must be the home page", result.stderr)

    def test_rejects_malformed_utf8_catalog(self) -> None:
        with tempfile.TemporaryDirectory(prefix="site-utf8-test-") as directory:
            root = Path(directory)
            source_root = self.create_canonical_source(root)
            catalog = source_root / "docs" / "publication-catalog.json"
            catalog.write_bytes(catalog.read_bytes() + b"\xff")
            result = self.run_assembler(source_root, root / "build")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("publication catalog must be valid UTF-8", result.stderr)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import assemble_publications
from scripts.publication_contract import (
    PublicationContractError,
    load_publication_catalog,
    parse_publication_catalog,
    safe_relative_path,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publication_contract.py"


class PublicationContractTests(unittest.TestCase):
    def write_catalog(self, root: Path, value: dict[str, object]) -> Path:
        path = root / "docs" / "publication-catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def base_catalog(self) -> dict[str, object]:
        return {
            "schema_version": 3,
            "documents": [
                {
                    "id": "overview",
                    "source": "README.md",
                    "optional": False,
                    "home": True,
                }
            ],
        }

    def create_valid_root(self, root: Path) -> None:
        (root / "README.md").write_text("# Example\n", encoding="utf-8")
        self.write_catalog(root, self.base_catalog())

    def test_valid_contract_is_loadable_and_standalone_cli_is_stdlib_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_valid_root(root)

            catalog = load_publication_catalog(root)
            self.assertEqual(
                [document.document_id for document in catalog.documents],
                ["overview"],
            )
            self.assertEqual(catalog.assets, ())
            self.assertIsNone(catalog.glossary_source)

            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(SCRIPT),
                    "--source-root",
                    str(root),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("validated schema-v3 publication contract", result.stdout)

    def test_strict_json_rejects_duplicate_members_and_nonstandard_constants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            docs.mkdir(parents=True)
            path = docs / "publication-catalog.json"
            path.write_text(
                '{"schema_version":3,"schema_version":3,"documents":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PublicationContractError,
                "duplicate object member: schema_version",
            ):
                parse_publication_catalog(path)

            path.write_text(
                '{"schema_version":NaN,"documents":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PublicationContractError,
                "non-standard numeric constant: NaN",
            ):
                parse_publication_catalog(path)

    def test_safe_path_rejects_cross_platform_escape_forms(self) -> None:
        invalid = (
            "",
            "../README.md",
            "docs/../README.md",
            "docs//README.md",
            "docs/./README.md",
            ".git/config",
            "docs/.GIT/config",
            "C:/README.md",
            "docs\\README.md",
            "/README.md",
            "docs/\0README.md",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(PublicationContractError):
                safe_relative_path(value, "test.path")

    def test_optional_missing_sources_are_allowed_but_required_sources_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            catalog = self.base_catalog()
            catalog["documents"] = [
                catalog["documents"][0],
                {
                    "id": "optional-page",
                    "source": "docs/optional.md",
                    "optional": True,
                    "home": False,
                },
            ]
            catalog["assets"] = [
                {
                    "source": "assets/optional",
                    "destination": "assets/optional",
                    "optional": True,
                }
            ]
            self.write_catalog(root, catalog)
            load_publication_catalog(root)

            catalog["documents"][1]["optional"] = False
            self.write_catalog(root, catalog)
            with self.assertRaisesRegex(
                PublicationContractError,
                "declared document source is not a regular file",
            ):
                load_publication_catalog(root)

    def test_symlinked_document_and_asset_tree_are_rejected_without_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            try:
                (root / "README.md").symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            self.write_catalog(root, self.base_catalog())
            with self.assertRaisesRegex(PublicationContractError, "symlink|symbolic link"):
                load_publication_catalog(root)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            assets = root / "assets"
            assets.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (outside / "secret.txt").write_text("secret\n", encoding="utf-8")
            try:
                (assets / "link").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            catalog = self.base_catalog()
            catalog["assets"] = [
                {
                    "source": "assets",
                    "destination": "assets",
                    "optional": False,
                }
            ]
            self.write_catalog(root, catalog)
            with self.assertRaisesRegex(PublicationContractError, "symlink|symbolic link"):
                load_publication_catalog(root)

    def test_assets_cannot_smuggle_markdown_or_use_markdown_file_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            assets = root / "assets"
            assets.mkdir()
            (assets / "hidden.md").write_text("hidden\n", encoding="utf-8")
            catalog = self.base_catalog()
            catalog["assets"] = [
                {
                    "source": "assets",
                    "destination": "assets",
                    "optional": False,
                }
            ]
            self.write_catalog(root, catalog)
            with self.assertRaisesRegex(
                PublicationContractError,
                "Markdown outside the document catalog",
            ):
                load_publication_catalog(root)

            (assets / "hidden.md").unlink()
            image = root / "logo.svg"
            image.write_text("<svg/>\n", encoding="utf-8")
            catalog["assets"] = [
                {
                    "source": "logo.svg",
                    "destination": "README.md",
                    "optional": False,
                }
            ]
            self.write_catalog(root, catalog)
            with self.assertRaisesRegex(
                PublicationContractError,
                "destination must not publish Markdown",
            ):
                load_publication_catalog(root)

    def test_asset_roots_and_destinations_must_not_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            catalog = self.base_catalog()
            catalog["assets"] = [
                {"source": "assets", "destination": "public", "optional": True},
                {
                    "source": "assets/icons",
                    "destination": "public/icons",
                    "optional": True,
                },
            ]
            path = self.write_catalog(root, catalog)
            with self.assertRaisesRegex(PublicationContractError, "asset sources must not overlap"):
                parse_publication_catalog(path)

            catalog["assets"] = [
                {"source": "a", "destination": "public", "optional": True},
                {
                    "source": "b",
                    "destination": "public/icons",
                    "optional": True,
                },
            ]
            path = self.write_catalog(root, catalog)
            with self.assertRaisesRegex(
                PublicationContractError,
                "asset destinations must not overlap",
            ):
                parse_publication_catalog(path)

    def test_glossary_source_is_validated_and_cannot_overlap_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            catalog = self.base_catalog()
            catalog["glossary"] = {"source": "docs/glossary.yml"}
            path = self.write_catalog(root, catalog)
            with self.assertRaisesRegex(
                PublicationContractError,
                "declared glossary source is not a regular file",
            ):
                load_publication_catalog(root)

            catalog["assets"] = [
                {
                    "source": "docs/glossary.yml",
                    "destination": "glossary.yml",
                    "optional": True,
                }
            ]
            path.write_text(json.dumps(catalog), encoding="utf-8")
            with self.assertRaisesRegex(
                PublicationContractError,
                "glossary source must not overlap asset sources",
            ):
                parse_publication_catalog(path)

    def test_assembler_load_catalog_delegates_to_materialization_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_valid_root(root)
            real_loader = assemble_publications.load_materialized_publication_catalog
            with mock.patch.object(
                assemble_publications,
                "load_materialized_publication_catalog",
                wraps=real_loader,
            ) as loader:
                documents, assets = assemble_publications.load_catalog("provider", root)

            loader.assert_called_once_with(root, "provider")
            self.assertEqual(set(documents), {"overview"})
            self.assertEqual(assets, [])


if __name__ == "__main__":
    unittest.main()

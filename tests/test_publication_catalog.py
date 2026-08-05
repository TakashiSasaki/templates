from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_publication_catalog import CatalogError, validate_catalog


class PublicationCatalogTests(unittest.TestCase):
    def write_catalog(self, root: Path, payload: object) -> Path:
        path = root / "docs" / "publication-catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_repository_catalog_is_valid(self) -> None:
        root = Path(__file__).resolve().parents[1]
        documents, assets = validate_catalog(
            root / "docs" / "publication-catalog.json",
            root,
        )
        self.assertGreater(len(documents), 0)
        self.assertGreaterEqual(len(assets), 0)

    def test_valid_version_2_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            (root / "assets").mkdir()
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 2,
                    "documents": [
                        {
                            "id": "overview",
                            "source": "README.md",
                            "optional": False,
                            "home": True,
                        }
                    ],
                    "assets": [
                        {
                            "source": "assets",
                            "destination": "assets",
                            "optional": False,
                        }
                    ],
                },
            )
            documents, assets = validate_catalog(catalog, root)
            self.assertEqual(
                ["overview"],
                [document.document_id for document in documents],
            )
            self.assertEqual(1, len(assets))

    def test_duplicate_json_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "docs" / "publication-catalog.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                '{"schema_version":2,"schema_version":1,"documents":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CatalogError, "duplicate object member"):
                validate_catalog(path, root)

    def test_overlapping_asset_destinations_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            (root / "one").mkdir()
            (root / "two").mkdir()
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 2,
                    "documents": [
                        {
                            "id": "overview",
                            "source": "README.md",
                            "optional": False,
                            "home": True,
                        }
                    ],
                    "assets": [
                        {
                            "source": "one",
                            "destination": "assets",
                            "optional": False,
                        },
                        {
                            "source": "two",
                            "destination": "assets/nested",
                            "optional": False,
                        },
                    ],
                },
            )
            with self.assertRaisesRegex(CatalogError, "destinations must not overlap"):
                validate_catalog(catalog, root)

    def test_boolean_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.write_catalog(
                root,
                {"schema_version": True, "documents": []},
            )
            with self.assertRaisesRegex(CatalogError, "integer 1 or 2"):
                validate_catalog(catalog, root)

    def test_duplicate_document_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.md").write_text("# One\n", encoding="utf-8")
            (root / "two.md").write_text("# Two\n", encoding="utf-8")
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 1,
                    "documents": [
                        {
                            "id": "same",
                            "source": "one.md",
                            "optional": False,
                            "home": True,
                        },
                        {
                            "id": "same",
                            "source": "two.md",
                            "optional": False,
                            "home": False,
                        },
                    ],
                },
            )
            with self.assertRaisesRegex(CatalogError, "document IDs must be unique"):
                validate_catalog(catalog, root)

    def test_markdown_inside_asset_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            assets = root / "assets"
            assets.mkdir()
            (assets / "undeclared.md").write_text("# Hidden\n", encoding="utf-8")
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 2,
                    "documents": [
                        {
                            "id": "overview",
                            "source": "README.md",
                            "optional": False,
                            "home": True,
                        }
                    ],
                    "assets": [
                        {
                            "source": "assets",
                            "destination": "assets",
                            "optional": False,
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(CatalogError, "contains Markdown"):
                validate_catalog(catalog, root)

    def test_asset_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            outside = root / "outside"
            outside.mkdir()
            (root / "assets").symlink_to(outside, target_is_directory=True)
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 2,
                    "documents": [
                        {
                            "id": "overview",
                            "source": "README.md",
                            "optional": False,
                            "home": True,
                        }
                    ],
                    "assets": [
                        {
                            "source": "assets",
                            "destination": "assets",
                            "optional": False,
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(CatalogError, "symbolic link"):
                validate_catalog(catalog, root)


if __name__ == "__main__":
    unittest.main()

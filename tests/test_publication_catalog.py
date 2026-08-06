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

    @staticmethod
    def valid_document(
        *,
        document_id: str = "overview",
        source: str = "README.md",
        optional: bool = False,
        home: bool = True,
    ) -> dict[str, object]:
        return {
            "id": document_id,
            "source": source,
            "optional": optional,
            "home": home,
        }

    @staticmethod
    def valid_asset(
        *,
        source: str = "assets",
        destination: str = "assets",
        optional: bool = False,
    ) -> dict[str, object]:
        return {
            "source": source,
            "destination": destination,
            "optional": optional,
        }

    def valid_v1_catalog(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "documents": [self.valid_document()],
        }

    def test_repository_catalog_is_valid(self) -> None:
        root = Path(__file__).resolve().parents[1]
        documents, assets = validate_catalog(
            root / "docs" / "publication-catalog.json",
            root,
        )
        self.assertGreater(len(documents), 0)
        self.assertEqual(
            {"template/contracts", "template/schemas"},
            {asset.source.as_posix() for asset in assets},
        )
        self.assertEqual(
            {"contracts", "schemas"},
            {asset.destination.as_posix() for asset in assets},
        )
        home = [document for document in documents if document.home]
        self.assertEqual(1, len(home))
        self.assertEqual("template/README.md", home[0].source.as_posix())

    def test_valid_version_1_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            catalog = self.write_catalog(root, self.valid_v1_catalog())
            documents, assets = validate_catalog(catalog, root)
            self.assertEqual(["overview"], [item.document_id for item in documents])
            self.assertEqual([], assets)

    def test_valid_version_2_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            (root / "assets").mkdir()
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 2,
                    "documents": [self.valid_document()],
                    "assets": [self.valid_asset()],
                },
            )
            documents, assets = validate_catalog(catalog, root)
            self.assertEqual(["overview"], [item.document_id for item in documents])
            self.assertEqual(1, len(assets))

    def test_missing_optional_sources_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 2,
                    "documents": [
                        self.valid_document(),
                        self.valid_document(
                            document_id="optional-guide",
                            source="docs/optional-guide.md",
                            optional=True,
                            home=False,
                        ),
                    ],
                    "assets": [
                        self.valid_asset(
                            source="optional-assets",
                            destination="optional-assets",
                            optional=True,
                        )
                    ],
                },
            )
            documents, assets = validate_catalog(catalog, root)
            self.assertEqual(2, len(documents))
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

    def test_version_1_assets_are_rejected_with_dedicated_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 1,
                    "documents": [self.valid_document()],
                    "assets": [],
                },
            )
            with self.assertRaisesRegex(
                CatalogError,
                "schema_version 1 does not support assets",
            ):
                validate_catalog(catalog, root)

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
                    "documents": [self.valid_document()],
                    "assets": [
                        self.valid_asset(source="one"),
                        self.valid_asset(
                            source="two",
                            destination="assets/nested",
                        ),
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
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 1,
                    "documents": [
                        self.valid_document(source="one.md"),
                        self.valid_document(source="two.md", home=False),
                    ],
                },
            )
            with self.assertRaisesRegex(CatalogError, "document IDs must be unique"):
                validate_catalog(catalog, root)

    def test_duplicate_document_sources_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 1,
                    "documents": [
                        self.valid_document(),
                        self.valid_document(document_id="second", home=False),
                    ],
                },
            )
            with self.assertRaisesRegex(CatalogError, "document sources must be unique"):
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
                    "documents": [self.valid_document()],
                    "assets": [self.valid_asset()],
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
                    "documents": [self.valid_document()],
                    "assets": [self.valid_asset()],
                },
            )
            with self.assertRaisesRegex(CatalogError, "symbolic link"):
                validate_catalog(catalog, root)

    def test_asset_git_subtree_is_rejected(self) -> None:
        for git_name in (".git", ".GIT"):
            with self.subTest(git_name=git_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "README.md").write_text("# Home\n", encoding="utf-8")
                git_dir = root / "assets" / git_name
                git_dir.mkdir(parents=True)
                (git_dir / "config").write_text("secret\n", encoding="utf-8")
                catalog = self.write_catalog(
                    root,
                    {
                        "schema_version": 2,
                        "documents": [self.valid_document()],
                        "assets": [self.valid_asset()],
                    },
                )
                with self.assertRaisesRegex(CatalogError, "nested .git subtree"):
                    validate_catalog(catalog, root)

    def test_asset_markdown_case_variants_are_rejected(self) -> None:
        for extension in (".md", ".MD", ".mD"):
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "README.md").write_text("# Home\n", encoding="utf-8")
                assets = root / "assets"
                assets.mkdir()
                (assets / f"hidden{extension}").write_text("# Hidden\n", encoding="utf-8")
                catalog = self.write_catalog(
                    root,
                    {
                        "schema_version": 2,
                        "documents": [self.valid_document()],
                        "assets": [self.valid_asset()],
                    },
                )
                with self.assertRaisesRegex(CatalogError, "contains Markdown"):
                    validate_catalog(catalog, root)


if __name__ == "__main__":
    unittest.main()

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

    def valid_v3_catalog(self) -> dict[str, object]:
        return {
            "schema_version": 3,
            "documents": [self.valid_document()],
        }

    def test_repository_catalog_is_valid(self) -> None:
        root = Path(__file__).resolve().parents[1]
        documents, assets = validate_catalog(
            root / "docs" / "publication-catalog.json",
            root,
        )
        self.assertGreater(len(documents), 0)
        self.assertGreaterEqual(len(assets), 0)

    def test_valid_version_3_catalog_with_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            (root / "assets").mkdir()
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 3,
                    "documents": [self.valid_document()],
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
                '{"schema_version":3,"schema_version":3,"documents":[]}',
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
                    "schema_version": 3,
                    "documents": [self.valid_document()],
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

    def test_retired_and_non_integer_schema_versions_are_rejected(self) -> None:
        for version in (1, 2, 4, True, "3", 3.0, None, [3]):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                catalog = self.write_catalog(
                    root,
                    {"schema_version": version, "documents": []},
                )
                with self.assertRaisesRegex(CatalogError, "integer 3"):
                    validate_catalog(catalog, root)

    def test_duplicate_document_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.md").write_text("# One\n", encoding="utf-8")
            (root / "two.md").write_text("# Two\n", encoding="utf-8")
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 3,
                    "documents": [
                        self.valid_document(
                            document_id="same",
                            source="one.md",
                        ),
                        self.valid_document(
                            document_id="same",
                            source="two.md",
                            home=False,
                        ),
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
                    "schema_version": 3,
                    "documents": [
                        self.valid_document(),
                        self.valid_document(
                            document_id="second",
                            home=False,
                        ),
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
                    "schema_version": 3,
                    "documents": [self.valid_document()],
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
                    "schema_version": 3,
                    "documents": [self.valid_document()],
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
                        "schema_version": 3,
                        "documents": [self.valid_document()],
                        "assets": [
                            {
                                "source": "assets",
                                "destination": "assets",
                                "optional": False,
                            }
                        ],
                    },
                )
                with self.assertRaisesRegex(CatalogError, "contains a \\.git subtree"):
                    validate_catalog(catalog, root)

    def test_missing_required_document_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.write_catalog(root, self.valid_v3_catalog())
            with self.assertRaisesRegex(CatalogError, "not a regular file"):
                validate_catalog(catalog, root)

    def test_missing_required_asset_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Home\n", encoding="utf-8")
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 3,
                    "documents": [self.valid_document()],
                    "assets": [
                        {
                            "source": "missing-assets",
                            "destination": "assets",
                            "optional": False,
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(CatalogError, "asset source does not exist"):
                validate_catalog(catalog, root)

    def test_sensitive_and_windows_ambiguous_paths_are_rejected(self) -> None:
        cases = (
            ".git/config.md",
            ".GIT/config.md",
            "C:outside.md",
            "docs/file.md:stream",
            "../outside.md",
            "docs//outside.md",
        )
        for source in cases:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                catalog = self.write_catalog(
                    root,
                    {
                        "schema_version": 3,
                        "documents": [self.valid_document(source=source)],
                    },
                )
                with self.assertRaisesRegex(CatalogError, "safe non-empty relative"):
                    validate_catalog(catalog, root)

    def test_document_contract_and_home_invariants_are_rejected(self) -> None:
        cases: tuple[tuple[str, dict[str, object], str], ...] = (
            (
                "invalid document ID",
                {
                    "schema_version": 3,
                    "documents": [self.valid_document(document_id="Overview")],
                },
                "lowercase kebab-case",
            ),
            (
                "non-Markdown source",
                {
                    "schema_version": 3,
                    "documents": [self.valid_document(source="README.txt")],
                },
                "Markdown file",
            ),
            (
                "missing home",
                {
                    "schema_version": 3,
                    "documents": [self.valid_document(home=False)],
                },
                "exactly one home",
            ),
            (
                "multiple homes",
                {
                    "schema_version": 3,
                    "documents": [
                        self.valid_document(),
                        self.valid_document(
                            document_id="second",
                            source="second.md",
                        ),
                    ],
                },
                "exactly one home",
            ),
            (
                "optional home",
                {
                    "schema_version": 3,
                    "documents": [self.valid_document(optional=True)],
                },
                "must not be optional",
            ),
        )
        for label, payload, message in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                catalog = self.write_catalog(root, payload)
                with self.assertRaisesRegex(CatalogError, message):
                    validate_catalog(catalog, root)

    def test_unknown_top_level_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = self.write_catalog(
                root,
                {
                    "schema_version": 3,
                    "documents": [self.valid_document()],
                    "assets": [],
                    "unexpected": True,
                },
            )
            with self.assertRaisesRegex(CatalogError, "unsupported top-level fields"):
                validate_catalog(catalog, root)


if __name__ == "__main__":
    unittest.main()

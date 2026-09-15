from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_repository_trees import RepositoryTreeError, manifest_destinations
from scripts.prepare_repository_tree_publication import PreparationError, augment_manifest


class RepositoryTreeManifestSchemaVersionTests(unittest.TestCase):
    def _site_with_manifest(self, manifest: dict[str, object]) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "site-manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        return temporary, root

    def test_repository_tree_projection_rejects_non_integer_schema_versions(self) -> None:
        for version in (3.0, "3", None, True):
            with self.subTest(version=version):
                temporary, root = self._site_with_manifest(
                    {"schema_version": version, "documents": [], "navigation": []}
                )
                with temporary:
                    with self.assertRaisesRegex(
                        RepositoryTreeError,
                        "schema_version must be an integer",
                    ):
                        manifest_destinations(root)

    def test_repository_tree_projection_rejects_unsupported_integer_schema_version(self) -> None:
        temporary, root = self._site_with_manifest(
            {"schema_version": 4, "documents": [], "navigation": []}
        )
        with temporary:
            with self.assertRaisesRegex(
                RepositoryTreeError,
                "unsupported site manifest schema_version: 4",
            ):
                manifest_destinations(root)

    def test_publication_preparation_rejects_non_integer_schema_versions(self) -> None:
        for version in (3.0, "3", None, True):
            with self.subTest(version=version):
                with self.assertRaisesRegex(
                    PreparationError,
                    "schema_version must be an integer",
                ):
                    augment_manifest(
                        {"schema_version": version, "documents": [], "navigation": []}
                    )

    def test_publication_preparation_rejects_unsupported_integer_schema_version(self) -> None:
        with self.assertRaisesRegex(
            PreparationError,
            "unsupported site manifest schema_version: 4",
        ):
            augment_manifest({"schema_version": 4, "documents": [], "navigation": []})


if __name__ == "__main__":
    unittest.main()

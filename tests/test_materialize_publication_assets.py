from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.materialize_publication_assets import (
    PublicationMaterializationError,
    materialize_publication,
)


class PublicationMaterializationTests(unittest.TestCase):
    def write_catalog(self, root: Path, *, version: int, source_kind: str | None) -> None:
        (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        asset = {
            "source": "generated/output.bin",
            "destination": "runtime/output.bin",
            "optional": False,
        }
        if source_kind is not None:
            asset["source_kind"] = source_kind
        catalog = {
            "schema_version": version,
            "documents": [
                {
                    "id": "overview",
                    "source": "README.md",
                    "optional": False,
                    "home": True,
                }
            ],
            "assets": [asset],
        }
        path = root / "docs" / "publication-catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(catalog), encoding="utf-8")

    def write_materializer(self, root: Path, *, fail: bool = False) -> None:
        path = root / "scripts" / "materialize_publication.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        if fail:
            body = "import sys\nprint('fixture failure', file=sys.stderr)\nraise SystemExit(7)\n"
        else:
            body = """from __future__ import annotations
import argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
args = parser.parse_args()
target = args.source_root / 'generated' / 'output.bin'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(b'deterministic fixture output')
"""
        path.write_text(body, encoding="utf-8")

    def test_v4_generated_asset_materializes_then_passes_strict_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual(
                b"deterministic fixture output",
                (root / "generated" / "output.bin").read_bytes(),
            )

    def test_v4_generated_asset_without_materializer_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            with self.assertRaisesRegex(
                PublicationMaterializationError,
                "declares generated publication assets",
            ):
                materialize_publication(root, "fixture")

    def test_materializer_failure_is_not_treated_as_optional(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root, fail=True)
            with self.assertRaisesRegex(
                PublicationMaterializationError,
                "publication materializer failed: fixture failure",
            ):
                materialize_publication(root, "fixture")

    def test_v3_conventional_materializer_is_supported_only_as_migration_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=3, source_kind=None)
            self.write_materializer(root)
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue((root / "generated" / "output.bin").is_file())

    def test_v3_without_materializer_retains_existing_strict_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=3, source_kind=None)
            with self.assertRaisesRegex(
                PublicationMaterializationError,
                "declared asset source does not exist",
            ):
                materialize_publication(root, "fixture")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.publication_contract import PublicationContractError
from scripts.publication_contract_v4 import (
    load_publication_catalog_v4,
    parse_publication_catalog_v4,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publication_contract_v4.py"


class PublicationContractV4Tests(unittest.TestCase):
    def catalog(self, *assets: dict[str, object]) -> dict[str, object]:
        return {
            "schema_version": 4,
            "documents": [
                {
                    "id": "overview",
                    "source": "README.md",
                    "optional": False,
                    "home": True,
                }
            ],
            "assets": list(assets),
        }

    def write_root(self, root: Path, catalog: dict[str, object]) -> Path:
        (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        path = root / "docs" / "publication-catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(catalog), encoding="utf-8")
        return path

    def asset(
        self,
        *,
        source: str = "generated/output.bin",
        destination: str = "runtime/output.bin",
        optional: bool = False,
        source_kind: str = "generated",
    ) -> dict[str, object]:
        return {
            "source": source,
            "destination": destination,
            "optional": optional,
            "source_kind": source_kind,
        }

    def test_v4_requires_explicit_source_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = self.asset()
            del raw["source_kind"]
            path = self.write_root(root, self.catalog(raw))
            with self.assertRaisesRegex(PublicationContractError, "missing required fields: source_kind"):
                parse_publication_catalog_v4(path)

            raw["source_kind"] = "mystery"
            path.write_text(json.dumps(self.catalog(raw)), encoding="utf-8")
            with self.assertRaisesRegex(PublicationContractError, "source_kind must be tracked or generated"):
                parse_publication_catalog_v4(path)

    def test_required_generated_asset_is_allowed_only_before_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_root(root, self.catalog(self.asset()))

            catalog = load_publication_catalog_v4(root, phase="source")
            self.assertEqual("generated", catalog.assets[0].source_kind)
            self.assertEqual(1, len(catalog.generated_assets))

            with self.assertRaisesRegex(PublicationContractError, "declared asset source does not exist"):
                load_publication_catalog_v4(root, phase="materialized")

            output = root / "generated" / "output.bin"
            output.parent.mkdir()
            output.write_bytes(b"deterministic-build-product")
            load_publication_catalog_v4(root, phase="materialized")

    def test_required_tracked_asset_must_exist_even_before_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_root(root, self.catalog(self.asset(source_kind="tracked")))
            with self.assertRaisesRegex(PublicationContractError, "declared asset source does not exist"):
                load_publication_catalog_v4(root, phase="source")

    def test_optional_and_source_kind_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_root(
                root,
                self.catalog(
                    self.asset(source="missing/tracked.bin", destination="a.bin", optional=True, source_kind="tracked"),
                    self.asset(source="missing/generated.bin", destination="b.bin", optional=True, source_kind="generated"),
                ),
            )
            catalog = load_publication_catalog_v4(root, phase="materialized")
            self.assertEqual(["tracked", "generated"], [asset.source_kind for asset in catalog.assets])

    def test_generated_sources_keep_existing_path_and_symlink_guards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_root(root, self.catalog(self.asset(source="../escape.bin")))
            with self.assertRaisesRegex(PublicationContractError, "safe non-empty relative POSIX path"):
                parse_publication_catalog_v4(path)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_root(root, self.catalog(self.asset()))
            outside = root / "outside.bin"
            outside.write_bytes(b"outside")
            generated = root / "generated"
            generated.mkdir()
            try:
                (generated / "output.bin").symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(PublicationContractError, "symbolic link|symlink"):
                load_publication_catalog_v4(root, phase="materialized")

    def test_cli_has_distinct_pre_and_post_materialization_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_root(root, self.catalog(self.asset()))
            pre = subprocess.run(
                [sys.executable, "-I", str(SCRIPT), "--source-root", str(root), "--phase", "source"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, pre.returncode, pre.stderr)
            self.assertIn("validated schema-v4 publication contract", pre.stdout)
            self.assertIn("generated=1", pre.stdout)

            post = subprocess.run(
                [sys.executable, "-I", str(SCRIPT), "--source-root", str(root), "--phase", "materialized"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, post.returncode)
            self.assertIn("declared asset source does not exist", post.stderr)


if __name__ == "__main__":
    unittest.main()

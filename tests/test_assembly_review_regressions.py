from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications import (
    OUTPUT_MARKER,
    AssemblyError,
    assemble,
)


class AssemblyReviewRegressionTests(unittest.TestCase):
    def create_site(
        self,
        root: Path,
        *,
        assets: list[dict[str, object]] | None = None,
    ) -> None:
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "index.md").write_text("# Home\n", encoding="utf-8")
        catalog: dict[str, object] = {
            "schema_version": 2 if assets is not None else 1,
            "documents": [
                {
                    "id": "home",
                    "source": "docs/index.md",
                    "optional": False,
                    "home": True,
                }
            ],
        }
        if assets is not None:
            catalog["assets"] = assets
        (root / "docs" / "publication-catalog.json").write_text(
            json.dumps(catalog),
            encoding="utf-8",
        )
        manifest = {
            "schema_version": 2,
            "home": {"publication": "site", "document": "home"},
            "navigation": [
                {
                    "title": "Home",
                    "publication": "site",
                    "document": "home",
                    "destination": "index.md",
                }
            ],
        }
        (root / "site-manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        (root / "zensical.template.toml").write_text(
            'site_name = "test"\nnav = __GENERATED_NAV__\n',
            encoding="utf-8",
        )

    def test_unmanaged_nonempty_output_is_not_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            output = base / "important"
            self.create_site(site)
            output.mkdir()
            retained = output / "keep.txt"
            retained.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(AssemblyError, "not managed"):
                assemble({"site": site}, site, output)

            self.assertEqual("keep", retained.read_text(encoding="utf-8"))

    def test_managed_output_can_be_rebuilt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            output = base / "build"
            self.create_site(site)

            assemble({"site": site}, site, output)
            self.assertTrue((output / OUTPUT_MARKER).is_file())
            (output / "stale.txt").write_text("stale", encoding="utf-8")

            assemble({"site": site}, site, output)

            self.assertFalse((output / "stale.txt").exists())
            self.assertTrue((output / "docs" / "index.md").is_file())

    def test_output_cannot_overlap_publication_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "site"
            self.create_site(site)

            with self.assertRaisesRegex(AssemblyError, "must not overlap"):
                assemble({"site": site}, site, site)

            self.assertTrue((site / "docs" / "index.md").is_file())

    def test_current_working_directory_cannot_be_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            retained = base / "keep.txt"
            self.create_site(site)
            retained.write_text("keep", encoding="utf-8")
            previous = Path.cwd()
            os.chdir(base)
            try:
                with self.assertRaisesRegex(
                    AssemblyError,
                    "current working directory",
                ):
                    assemble({"site": site}, site, Path("."))
            finally:
                os.chdir(previous)

            self.assertEqual("keep", retained.read_text(encoding="utf-8"))

    def test_asset_directory_symlink_is_rejected_without_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            output = base / "build"
            outside = base / "outside"
            self.create_site(
                site,
                assets=[
                    {
                        "source": "assets",
                        "destination": "assets",
                        "optional": False,
                    }
                ],
            )
            (site / "assets").mkdir()
            outside.mkdir()
            (outside / "secret.txt").write_text("secret", encoding="utf-8")
            try:
                (site / "assets" / "link").symlink_to(
                    outside,
                    target_is_directory=True,
                )
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")

            with self.assertRaisesRegex(AssemblyError, "contains a symlink"):
                assemble({"site": site}, site, output)

            self.assertFalse(
                (output / "docs" / "site" / "assets" / "link" / "secret.txt").exists()
            )


if __name__ == "__main__":
    unittest.main()

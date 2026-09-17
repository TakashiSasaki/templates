from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest

from integration.publication_contract import (
    Asset,
    Document,
    PublicationCatalog,
    PublicationContractError,
    asset_files,
    safe_relative_path,
    validate_publication_sources,
)
from integration.publication_model import AssemblyError, copy_asset, parse_manifest


ROOT = Path(__file__).resolve().parents[1]


def catalog(*, document: PurePosixPath, asset: PurePosixPath, optional: bool = False) -> PublicationCatalog:
    return PublicationCatalog(
        documents=(Document("intro", document, optional, True),),
        assets=(Asset(asset, PurePosixPath("assets"), optional),),
        glossary_source=None,
    )


class MaterializationContractTests(unittest.TestCase):
    def test_unsafe_source_paths_fail_closed(self) -> None:
        for value in ("../escape", "/absolute", "a\\b", ".git/config"):
            with self.subTest(value=value):
                with self.assertRaises(PublicationContractError):
                    safe_relative_path(value, "source")

    def test_asset_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "assets"
            assets.mkdir()
            (assets / "real.txt").write_text("real", encoding="utf-8")
            (assets / "link.txt").symlink_to(assets / "real.txt")
            with self.assertRaisesRegex(PublicationContractError, "symbolic link"):
                asset_files(root, PurePosixPath("assets"), "assets")

    def test_asset_files_have_stable_relative_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets/nested").mkdir(parents=True)
            for name in ("z.txt", "nested/a.txt", "b.txt"):
                path = root / "assets" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name, encoding="utf-8")
            files = asset_files(root, PurePosixPath("assets"), "assets")
            self.assertEqual(
                [path.relative_to(root / "assets").as_posix() for path in files],
                ["b.txt", "nested/a.txt", "z.txt"],
            )

    def test_required_source_missing_is_rejected_before_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(PublicationContractError, "document source"):
                validate_publication_sources(
                    root,
                    catalog(document=PurePosixPath("docs/missing.md"), asset=PurePosixPath("assets")),
                )

    def test_optional_source_absence_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(
                validate_publication_sources(
                    root,
                    catalog(
                        document=PurePosixPath("docs/missing.md"),
                        asset=PurePosixPath("assets/missing.txt"),
                        optional=True,
                    ),
                )
            )

    def test_copy_asset_rejects_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "data.json").write_text("{}", encoding="utf-8")
            destination = root / "destination"
            destination.mkdir()
            (destination / "data.json").write_text("old", encoding="utf-8")
            with self.assertRaisesRegex(AssemblyError, "output collision"):
                copy_asset(source, destination, "asset")

    def test_manifest_duplicate_destination_and_missing_navigation_target_fail(self) -> None:
        manifest = json.loads((ROOT / "site-manifest.json").read_text(encoding="utf-8"))
        duplicate = copy.deepcopy(manifest)
        duplicate["documents"][1]["destination"] = duplicate["documents"][0]["destination"]
        with self.assertRaisesRegex(AssemblyError, "duplicate document destination"):
            parse_manifest(duplicate)

        missing_route = copy.deepcopy(manifest)
        missing_route["navigation"]["use"][0]["children"].append(
            {
                "title": "Missing",
                "publication": "site",
                "document": "missing",
                "destination": "missing.md",
            }
        )
        with self.assertRaisesRegex(AssemblyError, "navigation"):
            parse_manifest(missing_route)


if __name__ == "__main__":
    unittest.main()

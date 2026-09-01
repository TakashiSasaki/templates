from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.publish_translations import (
    TranslationPublicationError,
    publish_translations,
)


def blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


class TranslationPublicationTests(unittest.TestCase):
    def prepare_publication(
        self,
        root: Path,
    ) -> tuple[
        dict[str, dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        (root / "docs" / "nested").mkdir(parents=True)
        (root / "docs" / "assets").mkdir(parents=True)
        (root / "translations" / "ja" / "docs" / "nested").mkdir(parents=True)

        canonical = {
            "overview": b"# Overview\n",
            "details": b"# Details\n",
            "english": b"# English only\n",
            "nested-guide": b"# Nested guide\n",
        }
        (root / "docs" / "overview.md").write_bytes(canonical["overview"])
        (root / "docs" / "details.md").write_bytes(canonical["details"])
        (root / "docs" / "english.md").write_bytes(canonical["english"])
        (root / "docs" / "nested" / "guide.md").write_bytes(
            canonical["nested-guide"]
        )
        (root / "docs" / "assets" / "example.txt").write_text(
            "asset\n",
            encoding="utf-8",
        )
        (root / "docs" / "assets" / "example.png").write_bytes(b"png")

        overview_translation = (
            "# 概要\n\n"
            "> **参考訳（非正本）:** test\n\n"
            "[translated](details.md)\n"
            "[canonical fallback](english.md)\n"
            "[fallback](../../../docs/english.md#section)\n"
            "[asset](../../../docs/assets/example.txt)\n"
            "![image](../../../docs/assets/example.png)\n"
            "[reference asset][asset-ref]\n"
            "[asset-ref]: ../../../docs/assets/example.txt\n"
            "[external](https://example.com/docs.md)\n"
            "```text\n[code](details.md)\n```\n"
        )
        details_translation = (
            "---\ndescription: translated\n---\n\n"
            "# 詳細\n\n> **参考訳（非正本）:** test\n"
        )
        nested_translation = (
            "# ネスト\n\n"
            "> **参考訳（非正本）:** test\n\n"
            "[parent asset](../../../../docs/assets/example.txt)\n"
            "![parent image](../../../../docs/assets/example.png)\n"
        )
        (root / "translations" / "ja" / "docs" / "overview.md").write_text(
            overview_translation,
            encoding="utf-8",
        )
        (root / "translations" / "ja" / "docs" / "details.md").write_text(
            details_translation,
            encoding="utf-8",
        )
        (
            root / "translations" / "ja" / "docs" / "nested" / "guide.md"
        ).write_text(nested_translation, encoding="utf-8")

        manifest = {
            "schema_version": 2,
            "canonical_language": "en",
            "translations": [
                {
                    "canonical": "docs/overview.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/overview.md",
                    "canonical_blob_sha": blob_sha(canonical["overview"]),
                    "surfaces": ["reader"],
                },
                {
                    "canonical": "docs/details.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/details.md",
                    "canonical_blob_sha": blob_sha(canonical["details"]),
                    "surfaces": ["reader"],
                },
                {
                    "canonical": "docs/nested/guide.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/nested/guide.md",
                    "canonical_blob_sha": blob_sha(canonical["nested-guide"]),
                    "surfaces": ["reader"],
                },
            ],
        }
        (root / "translations" / "manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

        documents = {
            "overview": {
                "source": PurePosixPath("docs/overview.md"),
                "optional": False,
                "home": True,
            },
            "details": {
                "source": PurePosixPath("docs/details.md"),
                "optional": False,
                "home": False,
            },
            "english": {
                "source": PurePosixPath("docs/english.md"),
                "optional": False,
                "home": False,
            },
            "nested-guide": {
                "source": PurePosixPath("docs/nested/guide.md"),
                "optional": False,
                "home": False,
            },
        }
        assets = [
            {
                "source": PurePosixPath("docs/assets"),
                "destination": PurePosixPath("assets"),
                "optional": False,
            }
        ]
        pages = [
            {
                "publication": "policy",
                "document": "overview",
                "destination": PurePosixPath("policy/index.md"),
            },
            {
                "publication": "policy",
                "document": "details",
                "destination": PurePosixPath("policy/details.md"),
            },
            {
                "publication": "policy",
                "document": "english",
                "destination": PurePosixPath("policy/english.md"),
            },
            {
                "publication": "policy",
                "document": "nested-guide",
                "destination": PurePosixPath("policy/nested/guide.md"),
            },
        ]
        return documents, assets, pages

    def publish(self, root: Path, output: Path) -> list[object]:
        documents, assets, pages = self.prepare_publication(root)
        docs_root = output / "docs"
        (docs_root / "policy").mkdir(parents=True)
        for page in pages:
            destination = page["destination"]
            assert isinstance(destination, PurePosixPath)
            target = docs_root.joinpath(*destination.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# canonical\n", encoding="utf-8")
        publications = {"policy": (root, documents, assets)}
        return publish_translations(publications, pages, docs_root)

    def test_declared_translations_publish_under_language_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            records = self.publish(base / "policy", base / "output")
            docs = base / "output" / "docs"

            self.assertEqual(len(records), 3)
            self.assertTrue((docs / "ja" / "policy" / "index.md").is_file())
            self.assertTrue((docs / "ja" / "policy" / "details.md").is_file())
            self.assertTrue(
                (docs / "ja" / "policy" / "nested" / "guide.md").is_file()
            )
            self.assertFalse((docs / "ja" / "policy" / "english.md").exists())

    def test_guided_only_entry_is_not_published_as_reader_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, assets, pages = self.prepare_publication(root)
            manifest_path = root / "translations" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["translations"][0]["surfaces"] = ["guided"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            records = publish_translations(
                {"policy": (root, documents, assets)},
                pages,
                docs_root,
            )
            self.assertEqual(len(records), 2)
            self.assertFalse((docs_root / "ja" / "policy" / "index.md").exists())

    def test_links_images_and_references_are_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            self.publish(base / "policy", base / "output")
            docs = base / "output" / "docs"
            overview = (docs / "ja" / "policy" / "index.md").read_text(
                encoding="utf-8"
            )
            nested = (docs / "ja" / "policy" / "nested" / "guide.md").read_text(
                encoding="utf-8"
            )

            self.assertIn("[translated](details.md)", overview)
            self.assertIn("[canonical fallback](../../policy/english.md)", overview)
            self.assertIn("[fallback](../../policy/english.md#section)", overview)
            self.assertIn("[asset](../../policy/assets/example.txt)", overview)
            self.assertIn("![image](../../policy/assets/example.png)", overview)
            self.assertIn("[asset-ref]: ../../policy/assets/example.txt", overview)
            self.assertIn("[external](https://example.com/docs.md)", overview)
            self.assertIn("[code](details.md)", overview)
            self.assertIn(
                "[parent asset](../../../policy/assets/example.txt)",
                nested,
            )
            self.assertIn(
                "![parent image](../../../policy/assets/example.png)",
                nested,
            )

    def test_translation_source_depth_controls_direct_canonical_asset_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            self.publish(base / "policy", base / "output")
            overview = (
                base / "output" / "docs" / "ja" / "policy" / "index.md"
            ).read_text(encoding="utf-8")
            self.assertIn("[asset](../../policy/assets/example.txt)", overview)

    def test_unmapped_translation_tree_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, assets, pages = self.prepare_publication(root)
            translated = root / "translations" / "ja" / "docs" / "overview.md"
            translated.write_text(
                translated.read_text(encoding="utf-8")
                + "[undeclared](missing.md)\n",
                encoding="utf-8",
            )
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)
            with self.assertRaisesRegex(
                TranslationPublicationError,
                "does not resolve to a published canonical document or asset",
            ):
                publish_translations(
                    {"policy": (root, documents, assets)}, pages, docs_root
                )

    def test_stale_translation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, assets, pages = self.prepare_publication(root)
            manifest_path = root / "translations" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["translations"][0]["canonical_blob_sha"] = "0" * 40
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            with self.assertRaisesRegex(TranslationPublicationError, "stale translation"):
                publish_translations(
                    {"policy": (root, documents, assets)},
                    pages,
                    docs_root,
                )

    def test_unmanifested_translation_is_not_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, assets, pages = self.prepare_publication(root)
            extra = root / "translations" / "ja" / "docs" / "english.md"
            extra.write_text(
                "# 追加\n\n> **参考訳（非正本）:** undeclared\n",
                encoding="utf-8",
            )
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            records = publish_translations(
                {"policy": (root, documents, assets)},
                pages,
                docs_root,
            )
            self.assertEqual(len(records), 3)
            self.assertFalse((docs_root / "ja" / "policy" / "english.md").exists())

    def test_mirrored_translation_path_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, assets, pages = self.prepare_publication(root)
            manifest_path = root / "translations" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["translations"][0]["translation"] = "translations/ja/overview.md"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            with self.assertRaisesRegex(TranslationPublicationError, "must mirror canonical"):
                publish_translations(
                    {"policy": (root, documents, assets)},
                    pages,
                    docs_root,
                )

    def test_float_manifest_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, assets, pages = self.prepare_publication(root)
            manifest_path = root / "translations" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["schema_version"] = 2.0
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            with self.assertRaisesRegex(
                TranslationPublicationError,
                "schema_version must be integer 2",
            ):
                publish_translations(
                    {"policy": (root, documents, assets)},
                    pages,
                    docs_root,
                )

    @unittest.skipIf(os.name == "nt", "symlink creation is not reliably available on Windows")
    def test_symlink_translation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, assets, pages = self.prepare_publication(root)
            translation = root / "translations" / "ja" / "docs" / "overview.md"
            target = translation.with_name("target.md")
            target.write_text(translation.read_text(encoding="utf-8"), encoding="utf-8")
            translation.unlink()
            translation.symlink_to(target.name)
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            with self.assertRaisesRegex(TranslationPublicationError, "must not traverse"):
                publish_translations(
                    {"policy": (root, documents, assets)},
                    pages,
                    docs_root,
                )

    @unittest.skipIf(os.name == "nt", "symlink creation is not reliably available on Windows")
    def test_broken_manifest_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, assets, pages = self.prepare_publication(root)
            manifest = root / "translations" / "manifest.json"
            manifest.unlink()
            manifest.symlink_to("missing-manifest.json")
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            with self.assertRaisesRegex(TranslationPublicationError, "must not traverse"):
                publish_translations(
                    {"policy": (root, documents, assets)},
                    pages,
                    docs_root,
                )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from scripts.publish_translations import (
    TranslationPublicationError,
    publish_translations,
)


def blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


class TranslationPublicationTests(unittest.TestCase):
    def prepare_publication(self, root: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
        (root / "docs").mkdir(parents=True)
        (root / "translations" / "ja" / "docs").mkdir(parents=True)

        canonical = {
            "overview": b"# Overview\n",
            "details": b"# Details\n",
            "english": b"# English only\n",
        }
        for name, content in canonical.items():
            (root / "docs" / f"{name}.md").write_bytes(content)

        overview_translation = (
            "# 概要\n\n"
            "> **参考訳（非正本）:** test\n\n"
            "[translated](details.md)\n"
            "[fallback](english.md#section)\n"
            "[asset](assets/example.txt)\n"
            "[external](https://example.com/docs.md)\n"
            "```text\n[code](details.md)\n```\n"
        )
        details_translation = (
            "---\ndescription: translated\n---\n\n"
            "# 詳細\n\n> **参考訳（非正本）:** test\n"
        )
        (root / "translations" / "ja" / "docs" / "overview.md").write_text(
            overview_translation,
            encoding="utf-8",
        )
        (root / "translations" / "ja" / "docs" / "details.md").write_text(
            details_translation,
            encoding="utf-8",
        )

        manifest = {
            "schema_version": 1,
            "canonical_language": "en",
            "translations": [
                {
                    "canonical": "docs/overview.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/overview.md",
                    "canonical_blob_sha": blob_sha(canonical["overview"]),
                },
                {
                    "canonical": "docs/details.md",
                    "language": "ja",
                    "translation": "translations/ja/docs/details.md",
                    "canonical_blob_sha": blob_sha(canonical["details"]),
                },
            ],
        }
        (root / "translations" / "manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

        documents: dict[str, object] = {
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
        }
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
        ]
        return documents, pages

    def publish(self, root: Path, output: Path) -> list[object]:
        documents, pages = self.prepare_publication(root)
        docs_root = output / "docs"
        (docs_root / "policy").mkdir(parents=True)
        for page in pages:
            destination = page["destination"]
            assert isinstance(destination, PurePosixPath)
            target = docs_root.joinpath(*destination.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# canonical\n", encoding="utf-8")
        publications = {"policy": (root, documents, [])}
        return publish_translations(publications, pages, docs_root)

    def test_declared_translations_publish_under_language_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            records = self.publish(base / "policy", base / "output")
            docs = base / "output" / "docs"

            self.assertEqual(len(records), 2)
            self.assertTrue((docs / "ja" / "policy" / "index.md").is_file())
            self.assertTrue((docs / "ja" / "policy" / "details.md").is_file())
            self.assertFalse((docs / "ja" / "policy" / "english.md").exists())

    def test_links_prefer_translation_and_fallback_to_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            self.publish(base / "policy", base / "output")
            text = (base / "output" / "docs" / "ja" / "policy" / "index.md").read_text(
                encoding="utf-8"
            )

            self.assertIn("[translated](details.md)", text)
            self.assertIn("[fallback](../../policy/english.md#section)", text)
            self.assertIn("[asset](../../policy/assets/example.txt)", text)
            self.assertIn("[external](https://example.com/docs.md)", text)
            self.assertIn("[code](details.md)", text)

    def test_stale_translation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, pages = self.prepare_publication(root)
            manifest_path = root / "translations" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["translations"][0]["canonical_blob_sha"] = "0" * 40
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            with self.assertRaisesRegex(TranslationPublicationError, "stale translation"):
                publish_translations({"policy": (root, documents, [])}, pages, docs_root)

    def test_unmanifested_translation_is_not_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, pages = self.prepare_publication(root)
            extra = root / "translations" / "ja" / "docs" / "english.md"
            extra.write_text(
                "# 追加\n\n> **参考訳（非正本）:** undeclared\n",
                encoding="utf-8",
            )
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            records = publish_translations(
                {"policy": (root, documents, [])},
                pages,
                docs_root,
            )
            self.assertEqual(len(records), 2)
            self.assertFalse((docs_root / "ja" / "policy" / "english.md").exists())

    def test_mirrored_translation_path_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, pages = self.prepare_publication(root)
            manifest_path = root / "translations" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["translations"][0]["translation"] = "translations/ja/overview.md"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            with self.assertRaisesRegex(TranslationPublicationError, "must mirror canonical"):
                publish_translations({"policy": (root, documents, [])}, pages, docs_root)

    @unittest.skipIf(os.name == "nt", "symlink creation is not reliably available on Windows")
    def test_symlink_translation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "policy"
            documents, pages = self.prepare_publication(root)
            translation = root / "translations" / "ja" / "docs" / "overview.md"
            target = translation.with_name("target.md")
            target.write_text(translation.read_text(encoding="utf-8"), encoding="utf-8")
            translation.unlink()
            translation.symlink_to(target.name)
            docs_root = base / "output" / "docs"
            docs_root.mkdir(parents=True)

            with self.assertRaisesRegex(TranslationPublicationError, "must not traverse"):
                publish_translations({"policy": (root, documents, [])}, pages, docs_root)


if __name__ == "__main__":
    unittest.main()

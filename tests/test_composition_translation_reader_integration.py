from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from scripts import publish_translations as translation_publisher


def blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


class CompositionTranslationReaderIntegrationTests(unittest.TestCase):
    def test_root_readme_reader_translation_publishes_to_composition_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            provider = base / "composition"
            output = base / "output" / "docs"
            (provider / "docs").mkdir(parents=True)
            (provider / "translations" / "ja").mkdir(parents=True)
            (output / "composition" / "use").mkdir(parents=True)

            overview = b"# Composition\n"
            guide = b"# Using Composition\n"
            (provider / "README.md").write_bytes(overview)
            (provider / "docs" / "consumer-guide.md").write_bytes(guide)
            (provider / "translations" / "ja" / "README.md").write_text(
                "# Composition\n\n"
                "> **参考訳（非正本）:** test\n\n"
                "[Using Composition](docs/consumer-guide.md)\n",
                encoding="utf-8",
            )
            (provider / "translations" / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "canonical_language": "en",
                        "translations": [
                            {
                                "canonical": "README.md",
                                "language": "ja",
                                "translation": "translations/ja/README.md",
                                "canonical_blob_sha": blob_sha(overview),
                                "surfaces": ["reader"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            documents = {
                "overview": {
                    "source": PurePosixPath("README.md"),
                    "optional": False,
                    "home": True,
                },
                "consumer-guide": {
                    "source": PurePosixPath("docs/consumer-guide.md"),
                    "optional": False,
                    "home": False,
                },
            }
            pages = [
                {
                    "publication": "composition",
                    "document": "overview",
                    "destination": PurePosixPath("composition/index.md"),
                },
                {
                    "publication": "composition",
                    "document": "consumer-guide",
                    "destination": PurePosixPath("composition/use/index.md"),
                },
            ]
            (output / "composition" / "index.md").write_bytes(overview)
            (output / "composition" / "use" / "index.md").write_bytes(guide)

            records = translation_publisher.publish_translations(
                {"composition": (provider, documents, [])},
                pages,
                output,
            )

            self.assertEqual(len(records), 1)
            translated = output / "ja" / "composition" / "index.md"
            self.assertTrue(translated.is_file())
            text = translated.read_text(encoding="utf-8")
            self.assertIn("> **参考訳（非正本）:**", text)
            self.assertIn("[Using Composition](../../composition/use/index.md)", text)
            self.assertEqual(
                records[0].canonical_destination,
                PurePosixPath("composition/index.md"),
            )
            self.assertEqual(
                records[0].translation_destination,
                PurePosixPath("ja/composition/index.md"),
            )

    def test_documentation_index_prefers_current_japanese_and_falls_back_to_english(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            provider = base / "composition"
            output = base / "output" / "docs"
            (provider / "docs" / "reference").mkdir(parents=True)
            (provider / "translations" / "ja" / "docs").mkdir(parents=True)
            (output / "composition" / "docs").mkdir(parents=True)
            (output / "composition" / "use").mkdir(parents=True)
            (output / "composition" / "reference").mkdir(parents=True)

            index = (
                b"# Composition documentation index\n\n"
                b"[Using Composition](consumer-guide.md)\n"
                b"[Composer reference](reference/composer.md)\n"
            )
            guide = b"# Using Composition\n"
            reference = b"# Composer reference\n"
            (provider / "docs" / "index.md").write_bytes(index)
            (provider / "docs" / "consumer-guide.md").write_bytes(guide)
            (provider / "docs" / "reference" / "composer.md").write_bytes(reference)
            (provider / "translations" / "ja" / "docs" / "index.md").write_text(
                "# Composition ドキュメント索引\n\n"
                "> **参考訳（非正本）:** test\n\n"
                "[Composition の利用方法](consumer-guide.md)\n"
                "[Composer リファレンス](reference/composer.md)\n",
                encoding="utf-8",
            )
            (provider / "translations" / "ja" / "docs" / "consumer-guide.md").write_text(
                "# Composition の利用方法\n\n"
                "> **参考訳（非正本）:** test\n",
                encoding="utf-8",
            )
            (provider / "translations" / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "canonical_language": "en",
                        "translations": [
                            {
                                "canonical": "docs/index.md",
                                "language": "ja",
                                "translation": "translations/ja/docs/index.md",
                                "canonical_blob_sha": blob_sha(index),
                                "surfaces": ["reader", "guided"],
                            },
                            {
                                "canonical": "docs/consumer-guide.md",
                                "language": "ja",
                                "translation": "translations/ja/docs/consumer-guide.md",
                                "canonical_blob_sha": blob_sha(guide),
                                "surfaces": ["reader"],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            documents = {
                "documentation-index": {
                    "source": PurePosixPath("docs/index.md"),
                    "optional": False,
                    "home": False,
                },
                "consumer-guide": {
                    "source": PurePosixPath("docs/consumer-guide.md"),
                    "optional": False,
                    "home": False,
                },
                "composer-reference": {
                    "source": PurePosixPath("docs/reference/composer.md"),
                    "optional": False,
                    "home": False,
                },
            }
            pages = [
                {
                    "publication": "composition",
                    "document": "documentation-index",
                    "destination": PurePosixPath("composition/docs/index.md"),
                },
                {
                    "publication": "composition",
                    "document": "consumer-guide",
                    "destination": PurePosixPath("composition/use/index.md"),
                },
                {
                    "publication": "composition",
                    "document": "composer-reference",
                    "destination": PurePosixPath("composition/reference/composer.md"),
                },
            ]
            (output / "composition" / "docs" / "index.md").write_bytes(index)
            (output / "composition" / "use" / "index.md").write_bytes(guide)
            (output / "composition" / "reference" / "composer.md").write_bytes(reference)

            records = translation_publisher.publish_translations(
                {"composition": (provider, documents, [])},
                pages,
                output,
            )

            self.assertEqual(len(records), 2)
            translated = output / "ja" / "composition" / "docs" / "index.md"
            self.assertTrue(translated.is_file())
            text = translated.read_text(encoding="utf-8")
            self.assertIn("[Composition の利用方法](../use/index.md)", text)
            self.assertIn(
                "[Composer リファレンス](../../../composition/reference/composer.md)",
                text,
            )


if __name__ == "__main__":
    unittest.main()

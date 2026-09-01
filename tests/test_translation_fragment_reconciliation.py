from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePosixPath

from scripts.publish_translations import TranslationRecord
from scripts.translation_fragment_reconciliation import (
    TranslationFragmentReconciliationError,
    reconcile_translation_fragments,
)


class TranslationFragmentReconciliationTests(unittest.TestCase):
    def prepare(
        self,
        base: Path,
        canonical_guide: str,
        published_translation: str,
    ) -> tuple[dict, list[dict], list[TranslationRecord], Path]:
        root = base / "composition"
        (root / "docs").mkdir(parents=True)
        (root / "translations" / "ja" / "docs").mkdir(parents=True)
        (root / "docs" / "guide.md").write_text(canonical_guide, encoding="utf-8")
        (root / "docs" / "consumer.md").write_text(
            "# Consumer\n\n## Install and run\n",
            encoding="utf-8",
        )
        translation_source = root / "translations" / "ja" / "docs" / "guide.md"
        translation_source.write_text("# 参考訳\n", encoding="utf-8")

        docs_root = base / "output" / "docs"
        translated_output = docs_root / "ja" / "composition" / "guide.md"
        translated_output.parent.mkdir(parents=True)
        translated_output.write_text(published_translation, encoding="utf-8")

        publications = {
            "composition": (
                root,
                {
                    "guide": {
                        "source": PurePosixPath("docs/guide.md"),
                        "optional": False,
                        "home": False,
                    },
                    "consumer": {
                        "source": PurePosixPath("docs/consumer.md"),
                        "optional": False,
                        "home": False,
                    },
                },
                [],
            )
        }
        included_pages = [
            {
                "publication": "composition",
                "document": "guide",
                "destination": PurePosixPath("composition/guide.md"),
            },
            {
                "publication": "composition",
                "document": "consumer",
                "destination": PurePosixPath("composition/consumer.md"),
            },
        ]
        records = [
            TranslationRecord(
                publication="composition",
                language="ja",
                canonical_source=PurePosixPath("docs/guide.md"),
                translation_source=PurePosixPath("translations/ja/docs/guide.md"),
                canonical_destination=PurePosixPath("composition/guide.md"),
                translation_destination=PurePosixPath("ja/composition/guide.md"),
                source_file=translation_source,
            )
        ]
        return publications, included_pages, records, docs_root

    def test_unique_canonical_fragment_repairs_stale_translation_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            state = self.prepare(
                base,
                "# Guide\n\n[Install](consumer.md#install-and-run-the-composition-skill)\n",
                "# ガイド\n\n[利用](../../composition/consumer.md#composition-skill-install)\n",
            )

            changed = reconcile_translation_fragments(*state)

            self.assertEqual(changed, 1)
            translated = (
                state[3] / "ja" / "composition" / "guide.md"
            ).read_text(encoding="utf-8")
            self.assertIn(
                "[利用](../../composition/consumer.md#install-and-run-the-composition-skill)",
                translated,
            )
            self.assertNotIn("#composition-skill-install", translated)

    def test_matching_canonical_fragment_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            state = self.prepare(
                base,
                "# Guide\n\n[Install](consumer.md#install-and-run)\n",
                "# ガイド\n\n[利用](../../composition/consumer.md#install-and-run)\n",
            )

            changed = reconcile_translation_fragments(*state)

            self.assertEqual(changed, 0)

    def test_multiple_canonical_fragments_for_one_target_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            state = self.prepare(
                base,
                (
                    "# Guide\n\n"
                    "[First](consumer.md#first)\n"
                    "[Second](consumer.md#second)\n"
                ),
                "# ガイド\n\n[利用](../../composition/consumer.md#old)\n",
            )

            with self.assertRaisesRegex(
                TranslationFragmentReconciliationError,
                "multiple canonical candidates",
            ):
                reconcile_translation_fragments(*state)

    def test_translation_only_target_without_canonical_fragment_evidence_is_not_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            state = self.prepare(
                base,
                "# Guide\n\n[Consumer](consumer.md)\n",
                "# ガイド\n\n[追加](../../composition/consumer.md#translation-only)\n",
            )

            changed = reconcile_translation_fragments(*state)

            self.assertEqual(changed, 0)
            translated = (
                state[3] / "ja" / "composition" / "guide.md"
            ).read_text(encoding="utf-8")
            self.assertIn("#translation-only", translated)

    def test_fenced_example_is_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            state = self.prepare(
                base,
                "# Guide\n\n[Install](consumer.md#canonical)\n",
                (
                    "# ガイド\n\n"
                    "```md\n"
                    "[sample](../../composition/consumer.md#old)\n"
                    "```\n"
                    "[real](../../composition/consumer.md#old)\n"
                ),
            )

            changed = reconcile_translation_fragments(*state)

            self.assertEqual(changed, 1)
            translated = (
                state[3] / "ja" / "composition" / "guide.md"
            ).read_text(encoding="utf-8")
            self.assertIn("[sample](../../composition/consumer.md#old)", translated)
            self.assertIn("[real](../../composition/consumer.md#canonical)", translated)


if __name__ == "__main__":
    unittest.main()

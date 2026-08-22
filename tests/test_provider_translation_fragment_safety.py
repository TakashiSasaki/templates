from __future__ import annotations

import unittest
from pathlib import Path, PurePosixPath

from scripts.publish_translations import TranslationRecord, _rewrite_markdown


class ProviderTranslationFragmentSafetyTests(unittest.TestCase):
    def test_cross_page_fragments_stay_canonical_while_plain_links_localize(self) -> None:
        record = TranslationRecord(
            publication="composition",
            language="ja",
            canonical_source=PurePosixPath("docs/index.md"),
            translation_source=PurePosixPath("translations/ja/docs/index.md"),
            canonical_destination=PurePosixPath("composition/docs/index.md"),
            translation_destination=PurePosixPath("ja/composition/docs/index.md"),
            source_file=Path("translations/ja/docs/index.md"),
        )
        canonical_destinations = {
            ("composition", PurePosixPath("docs/index.md")):
                PurePosixPath("composition/docs/index.md"),
            ("composition", PurePosixPath("docs/reference/composer.md")):
                PurePosixPath("composition/reference/composer.md"),
        }
        translated_destinations = {
            ("composition", "ja", PurePosixPath("docs/index.md")):
                PurePosixPath("ja/composition/docs/index.md"),
            ("composition", "ja", PurePosixPath("docs/reference/composer.md")):
                PurePosixPath("ja/composition/reference/composer.md"),
        }
        source = (
            "[plain](reference/composer.md)\n"
            "[fragment](reference/composer.md#installation)\n"
            "[reference][composer]\n"
            "[composer]: reference/composer.md?mode=full#installation\n"
            "[same](#local-section)\n"
        )

        rewritten = _rewrite_markdown(
            source,
            record,
            canonical_destinations,
            translated_destinations,
            {"composition": []},
        )

        self.assertIn("[plain](../reference/composer.md)", rewritten)
        self.assertIn(
            "[fragment](../../../composition/reference/composer.md#installation)",
            rewritten,
        )
        self.assertIn(
            "[composer]: ../../../composition/reference/composer.md?mode=full#installation",
            rewritten,
        )
        self.assertIn("[same](#local-section)", rewritten)


if __name__ == "__main__":
    unittest.main()

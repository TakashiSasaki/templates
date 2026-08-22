from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.reader_navigation_locales import ReaderNavigationLocaleError, load_overlays


class ReaderNavigationLocaleRejectionTests(unittest.TestCase):
    def write(self, path: Path, language: str, localized: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "canonical_language": "en",
                    "locales": [
                        {
                            "language": language,
                            "labels": [
                                {
                                    "id": "home",
                                    "canonical": "Home",
                                    "localized": localized,
                                }
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_invalid_language_tags_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            for language in ("JA", "ja_JP", "en"):
                with self.subTest(language=language):
                    self.write(path, language, "ホーム")
                    with self.assertRaisesRegex(
                        ReaderNavigationLocaleError,
                        "non-English lowercase language tag",
                    ):
                        load_overlays(path, [{"title": "Home"}])

    def test_whitespace_only_localized_label_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            self.write(path, "ja", "   ")

            with self.assertRaisesRegex(
                ReaderNavigationLocaleError,
                "localized must be a non-empty string",
            ):
                load_overlays(path, [{"title": "Home"}])


if __name__ == "__main__":
    unittest.main()

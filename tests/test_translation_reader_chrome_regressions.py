from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from finalize_translation_reader import (  # noqa: E402
    TranslationReaderError,
    canonical_switcher_markup,
    finalize,
    load_pairs,
    translated_switcher_markup,
)
from site_chrome_locales import SITE_CHROME_LOCALES, load_site_chrome_locales  # noqa: E402


HTML = """<!doctype html>
<html lang="en">
<head><link rel="canonical" href="https://templates.moukaeritai.work/"></head>
<body><main><h1>CLI</h1></main></body>
</html>
"""


class TranslationReaderChromeRegressionTests(unittest.TestCase):
    def test_switcher_text_language_is_distinct_from_target_language(self) -> None:
        chrome = load_site_chrome_locales(SITE_CHROME_LOCALES)

        canonical = canonical_switcher_markup(
            "policy",
            [("ja", "https://templates.moukaeritai.work/ja/policy/cli/")],
            chrome,
        )
        japanese = translated_switcher_markup(
            "policy",
            "ja",
            "https://templates.moukaeritai.work/policy/cli/",
            chrome,
        )
        french = translated_switcher_markup(
            "policy",
            "fr",
            "https://templates.moukaeritai.work/policy/cli/",
            chrome,
        )

        self.assertIn('lang="ja" hreflang="ja">日本語</a>', canonical)
        self.assertIn('lang="ja" hreflang="en">英語 · 正本</a>', japanese)
        self.assertIn('lang="en" hreflang="en">English · Canonical</a>', french)

    def test_finalize_uses_explicit_site_chrome_registry_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            canonical = site / "policy/cli/index.html"
            translated = site / "ja/policy/cli/index.html"
            canonical.parent.mkdir(parents=True)
            translated.parent.mkdir(parents=True)
            canonical.write_text(HTML, encoding="utf-8")
            translated.write_text(HTML, encoding="utf-8")

            mapping = root / "translation-publication.json"
            mapping.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "canonical_language": "en",
                        "translations": [
                            {
                                "publication": "policy",
                                "language": "ja",
                                "canonical_destination": "policy/cli.md",
                                "translation_destination": "ja/policy/cli.md",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            glossary_inline = {
                "eyebrow": "Glossary",
                "close_definition": "Close definition",
                "open_in_glossary": "Open in Glossary",
                "definition_unavailable": "Definition unavailable.",
                "cached_unverified": "Saved glossary data · latest version not verified.",
                "external_term_prefix": "External term · curated by",
                "repository_term_prefix": "Templates-defined ·",
                "data_unavailable": "Glossary data unavailable.",
                "definition_load_failed": "Definition could not be loaded.",
                "definition_not_found": "Definition could not be found.",
            }
            registry = root / "custom-chrome.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "canonical_language": "en",
                        "locales": [
                            {
                                "language": "en",
                                "language_label": "English",
                                "translation_reader": {
                                    "group_label": "Document language",
                                    "canonical_status": "Canonical English",
                                    "canonical_link": "English · Canonical",
                                    "translation_status": "English translation · Non-authoritative",
                                },
                                "pwa_freshness": {
                                    "saved_copy": "Saved copy.",
                                    "checking": "Checking.",
                                    "unverified": "Unverified.",
                                    "update_available": "Update available.",
                                    "published_changed": "Published page changed.",
                                    "reload": "Reload",
                                    "offline_unavailable": "Unavailable offline.",
                                },
                                "glossary_inline": glossary_inline,
                            },
                            {
                                "language": "ja",
                                "language_label": "日本語",
                                "translation_reader": {
                                    "group_label": "カスタム文書言語",
                                    "canonical_status": "英語正本",
                                    "canonical_link": "カスタム英語正本",
                                    "translation_status": "カスタム参考訳",
                                },
                                "pwa_freshness": {
                                    "saved_copy": "保存済み。",
                                    "checking": "確認中。",
                                    "unverified": "未確認。",
                                    "update_available": "更新あり。",
                                    "published_changed": "公開ページ更新。",
                                    "reload": "再読込",
                                    "offline_unavailable": "オフライン。",
                                },
                                "glossary_inline": glossary_inline,
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            finalize(
                site,
                mapping,
                "https://templates.moukaeritai.work/",
                registry,
            )

            rendered = translated.read_text(encoding="utf-8")
            self.assertIn('aria-label="カスタム文書言語"', rendered)
            self.assertIn("Policy · カスタム参考訳", rendered)
            self.assertIn("カスタム英語正本", rendered)

    def test_english_family_translation_tag_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translation-publication.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "canonical_language": "en",
                        "translations": [
                            {
                                "publication": "policy",
                                "language": "en-us",
                                "canonical_destination": "policy/cli.md",
                                "translation_destination": "en-us/policy/cli.md",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                TranslationReaderError,
                "non-English lowercase language tag",
            ):
                load_pairs(path)


if __name__ == "__main__":
    unittest.main()

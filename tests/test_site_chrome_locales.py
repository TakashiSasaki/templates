from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from site_chrome_locales import (  # noqa: E402
    SITE_CHROME_LOCALES,
    SiteChromeLocaleError,
    glossary_inline_strings,
    language_label,
    load_site_chrome_locales,
    pwa_freshness_strings,
    reader_strings,
    translation_status,
)


class SiteChromeLocaleTests(unittest.TestCase):
    def glossary_strings(self, language: str) -> dict[str, str]:
        if language == "ja":
            return {
                "eyebrow": "用語集",
                "close_definition": "定義を閉じる",
                "open_in_glossary": "用語集で開く",
                "definition_unavailable": "定義を利用できません。",
                "cached_unverified": "保存済みの用語集データ · 最新版であることを確認できませんでした。",
                "external_term_prefix": "外部用語 · 整理:",
                "repository_term_prefix": "テンプレート定義 ·",
                "data_unavailable": "用語集データを利用できません。",
                "definition_load_failed": "定義を読み込めませんでした。",
                "definition_not_found": "定義が見つかりませんでした。",
            }
        return {
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

    def payload(self) -> dict[str, object]:
        return {
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
                        "checking": "Checking for the latest version…",
                        "unverified": "The latest version could not be verified.",
                        "update_available": "Update available.",
                        "published_changed": "The published page changed.",
                        "reload": "Reload",
                        "offline_unavailable": "This page is unavailable while offline.",
                    },
                    "glossary_inline": self.glossary_strings("en"),
                },
                {
                    "language": "ja",
                    "language_label": "日本語",
                    "translation_reader": {
                        "group_label": "文書の言語",
                        "canonical_status": "英語正本",
                        "canonical_link": "英語 · 正本",
                        "translation_status": "日本語参考訳",
                    },
                    "pwa_freshness": {
                        "saved_copy": "保存済みのコピーです。",
                        "checking": "最新版を確認しています…",
                        "unverified": "最新版であることを確認できませんでした。",
                        "update_available": "更新があります。",
                        "published_changed": "公開済みページが更新されました。",
                        "reload": "再読み込み",
                        "offline_unavailable": "オフラインのため、このページを表示できません。",
                    },
                    "glossary_inline": self.glossary_strings("ja"),
                },
            ],
        }

    def write(self, path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_repository_registry_has_canonical_and_japanese_reader_chrome(self) -> None:
        model = load_site_chrome_locales(SITE_CHROME_LOCALES)
        self.assertEqual(model["canonical_language"], "en")
        self.assertEqual(language_label(model, "ja"), "日本語")
        self.assertEqual(reader_strings(model, "ja")["group_label"], "文書の言語")
        self.assertEqual(reader_strings(model, "ja")["canonical_link"], "英語 · 正本")
        self.assertEqual(translation_status(model, "ja"), "日本語参考訳")

    def test_repository_registry_has_canonical_and_japanese_pwa_freshness_chrome(self) -> None:
        model = load_site_chrome_locales(SITE_CHROME_LOCALES)
        self.assertEqual(pwa_freshness_strings(model, "en")["reload"], "Reload")
        self.assertEqual(
            pwa_freshness_strings(model, "ja")["offline_unavailable"],
            "オフラインのため、このページを表示できません。",
        )

    def test_repository_registry_has_canonical_and_japanese_glossary_chrome(self) -> None:
        model = load_site_chrome_locales(SITE_CHROME_LOCALES)
        self.assertEqual(glossary_inline_strings(model, "en")["eyebrow"], "Glossary")
        self.assertEqual(glossary_inline_strings(model, "ja")["eyebrow"], "用語集")
        self.assertEqual(
            glossary_inline_strings(model, "ja")["close_definition"],
            "定義を閉じる",
        )
        self.assertEqual(
            glossary_inline_strings(model, "ja")["open_in_glossary"],
            "用語集で開く",
        )

    def test_primary_language_fallback_is_used_for_registered_locale(self) -> None:
        model = load_site_chrome_locales(SITE_CHROME_LOCALES)
        self.assertEqual(language_label(model, "ja-jp"), "日本語")
        self.assertEqual(reader_strings(model, "ja-jp")["group_label"], "文書の言語")
        self.assertEqual(pwa_freshness_strings(model, "ja-jp")["reload"], "再読み込み")
        self.assertEqual(glossary_inline_strings(model, "ja-jp")["eyebrow"], "用語集")
        self.assertEqual(translation_status(model, "ja-jp"), "日本語参考訳")

    def test_unknown_language_uses_canonical_chrome_and_generic_status(self) -> None:
        model = load_site_chrome_locales(SITE_CHROME_LOCALES)
        self.assertEqual(language_label(model, "fr"), "fr")
        self.assertEqual(reader_strings(model, "fr")["group_label"], "Document language")
        self.assertEqual(pwa_freshness_strings(model, "fr")["reload"], "Reload")
        self.assertEqual(glossary_inline_strings(model, "fr")["eyebrow"], "Glossary")
        self.assertEqual(
            translation_status(model, "fr"),
            "fr translation · Non-authoritative",
        )

    def test_schema_and_root_shape_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            valid = self.payload()
            cases = (
                ({**valid, "schema_version": True}, "schema_version must be integer 1"),
                ({**valid, "schema_version": 2}, "schema_version must be integer 1"),
                ({**valid, "extra": True}, "must contain schema_version"),
                ({**valid, "canonical_language": "EN"}, "canonical_language must be en"),
                ({**valid, "canonical_language": "fr"}, "canonical_language must be en"),
                ({**valid, "locales": []}, "non-empty array"),
            )
            for payload, message in cases:
                with self.subTest(message=message):
                    self.write(path, payload)
                    with self.assertRaisesRegex(SiteChromeLocaleError, message):
                        load_site_chrome_locales(path)

    def test_locale_shape_duplicate_language_and_blank_strings_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            valid = self.payload()

            duplicate = json.loads(json.dumps(valid))
            duplicate["locales"].append(duplicate["locales"][0])
            self.write(path, duplicate)
            with self.assertRaisesRegex(SiteChromeLocaleError, "duplicate Site chrome locale"):
                load_site_chrome_locales(path)

            invalid_language = json.loads(json.dumps(valid))
            invalid_language["locales"][1]["language"] = "JA"
            self.write(path, invalid_language)
            with self.assertRaisesRegex(SiteChromeLocaleError, "lowercase language tag"):
                load_site_chrome_locales(path)

            for section, field_name in (
                ("translation_reader", "canonical_link"),
                ("pwa_freshness", "offline_unavailable"),
                ("glossary_inline", "open_in_glossary"),
            ):
                blank = json.loads(json.dumps(valid))
                blank["locales"][1][section][field_name] = "   "
                self.write(path, blank)
                with self.subTest(section=section):
                    with self.assertRaisesRegex(
                        SiteChromeLocaleError,
                        rf"{section}.{field_name}",
                    ):
                        load_site_chrome_locales(path)

    def test_chrome_sections_must_have_exact_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            for section, field_name in (
                ("translation_reader", "group_label"),
                ("pwa_freshness", "offline_unavailable"),
                ("glossary_inline", "eyebrow"),
            ):
                for mutation in ("missing", "extra"):
                    payload = self.payload()
                    fields = payload["locales"][1][section]  # type: ignore[index]
                    if mutation == "missing":
                        del fields[field_name]
                    else:
                        fields["extra_field"] = "extra"
                    with self.subTest(section=section, mutation=mutation):
                        self.write(path, payload)
                        with self.assertRaisesRegex(
                            SiteChromeLocaleError,
                            rf"{section} must contain",
                        ):
                            load_site_chrome_locales(path)

    def test_missing_required_chrome_section_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            for section in ("pwa_freshness", "glossary_inline"):
                payload = self.payload()
                del payload["locales"][1][section]  # type: ignore[index]
                self.write(path, payload)
                with self.subTest(section=section):
                    with self.assertRaisesRegex(SiteChromeLocaleError, "must contain language"):
                        load_site_chrome_locales(path)

    def test_missing_canonical_locale_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            payload = self.payload()
            payload["locales"] = [payload["locales"][1]]  # type: ignore[index]
            self.write(path, payload)
            with self.assertRaisesRegex(
                SiteChromeLocaleError,
                "must include the canonical language locale",
            ):
                load_site_chrome_locales(path)

    def test_duplicate_json_members_malformed_json_and_non_object_root_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            path.write_text(
                '{"schema_version":1,"schema_version":1,"canonical_language":"en","locales":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SiteChromeLocaleError, "duplicate member"):
                load_site_chrome_locales(path)
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(SiteChromeLocaleError, "unable to parse"):
                load_site_chrome_locales(path)
            self.write(path, [])
            with self.assertRaisesRegex(SiteChromeLocaleError, "must be an object"):
                load_site_chrome_locales(path)


if __name__ == "__main__":
    unittest.main()

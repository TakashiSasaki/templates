from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from finalize_translation_reader import (  # noqa: E402
    TranslationReaderError,
    finalize,
    replace_alternates,
    replace_html_language,
)
from publish_provider_translations import write_publication_map  # noqa: E402
from publish_translations import TranslationRecord  # noqa: E402


HTML = """<!doctype html>
<html lang="en" class="no-js">
<head>
<link rel="canonical" href="https://templates.moukaeritai.work/">
</head>
<body><main><h1 id="title">{title}</h1><p>{body}</p></main></body>
</html>
"""


class TranslationReaderTests(unittest.TestCase):
    def prepare_site(self, root: Path) -> Path:
        pages = {
            "policy/cli/index.html": ("CLI", "English"),
            "ja/policy/cli/index.html": ("CLI", "日本語"),
            "policy/adoption/index.html": ("Adoption", "English only"),
            "index.html": ("Home", "Home"),
        }
        for relative, (title, body) in pages.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(HTML.format(title=title, body=body), encoding="utf-8")
        mapping = {
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
        map_path = root.parent / "translation-publication.json"
        map_path.write_text(json.dumps(mapping), encoding="utf-8")
        return map_path

    def test_switcher_and_language_metadata_are_paired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            site.mkdir()
            map_path = self.prepare_site(site)

            page_count, pair_count = finalize(
                site,
                map_path,
                "https://templates.moukaeritai.work/",
            )

            self.assertEqual(page_count, 4)
            self.assertEqual(pair_count, 1)
            canonical = (site / "policy/cli/index.html").read_text(encoding="utf-8")
            translation = (site / "ja/policy/cli/index.html").read_text(encoding="utf-8")

            self.assertIn('lang="en"', canonical)
            self.assertIn("Policy · Canonical English", canonical)
            self.assertIn('aria-label="Document language"', canonical)
            self.assertIn(
                'href="https://templates.moukaeritai.work/ja/policy/cli/"',
                canonical,
            )
            self.assertIn(">日本語</a>", canonical)
            self.assertIn('hreflang="ja"', canonical)
            self.assertIn(
                '<link rel="canonical" href="https://templates.moukaeritai.work/policy/cli/">',
                canonical,
            )

            self.assertIn('lang="ja"', translation)
            self.assertIn("Policy · 日本語参考訳", translation)
            self.assertIn('aria-label="文書の言語"', translation)
            self.assertIn("英語 · 正本", translation)
            self.assertNotIn("English · Canonical", translation)
            self.assertIn(
                '<link rel="canonical" href="https://templates.moukaeritai.work/policy/cli/">',
                translation,
            )
            self.assertIn('hreflang="en"', translation)
            self.assertIn('hreflang="ja"', translation)

    def test_multiple_languages_share_one_canonical_switcher_and_alternates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            site.mkdir()
            map_path = self.prepare_site(site)
            french = site / "fr/policy/cli/index.html"
            french.parent.mkdir(parents=True)
            french.write_text(HTML.format(title="CLI", body="Français"), encoding="utf-8")
            mapping = json.loads(map_path.read_text(encoding="utf-8"))
            mapping["translations"].append(
                {
                    "publication": "policy",
                    "language": "fr",
                    "canonical_destination": "policy/cli.md",
                    "translation_destination": "fr/policy/cli.md",
                }
            )
            map_path.write_text(json.dumps(mapping), encoding="utf-8")

            page_count, pair_count = finalize(
                site,
                map_path,
                "https://templates.moukaeritai.work/",
            )

            self.assertEqual(page_count, 5)
            self.assertEqual(pair_count, 2)
            canonical = (site / "policy/cli/index.html").read_text(encoding="utf-8")
            japanese = (site / "ja/policy/cli/index.html").read_text(encoding="utf-8")
            french_text = french.read_text(encoding="utf-8")

            self.assertEqual(canonical.count('class="translation-switcher"'), 1)
            self.assertIn(">fr</a>", canonical)
            self.assertIn(">日本語</a>", canonical)
            for rendered in (canonical, japanese, french_text):
                self.assertIn('hreflang="en"', rendered)
                self.assertIn('hreflang="fr"', rendered)
                self.assertIn('hreflang="ja"', rendered)
            self.assertIn('lang="fr"', french_text)
            self.assertIn("Policy · fr translation · Non-authoritative", french_text)
            self.assertIn('aria-label="Document language"', french_text)
            self.assertIn("English · Canonical", french_text)

    def test_kebab_case_publication_label_is_humanized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            site.mkdir()
            map_path = self.prepare_site(site)
            mapping = json.loads(map_path.read_text(encoding="utf-8"))
            mapping["translations"][0]["publication"] = "shared-policy"
            map_path.write_text(json.dumps(mapping), encoding="utf-8")

            finalize(site, map_path, "https://templates.moukaeritai.work/")

            canonical = (site / "policy/cli/index.html").read_text(encoding="utf-8")
            self.assertIn("Shared Policy · Canonical English", canonical)

    def test_untranslated_page_has_self_canonical_and_no_switcher(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            site.mkdir()
            map_path = self.prepare_site(site)

            finalize(site, map_path, "https://templates.moukaeritai.work/")

            untranslated = (site / "policy/adoption/index.html").read_text(
                encoding="utf-8"
            )
            home = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn(
                '<link rel="canonical" href="https://templates.moukaeritai.work/policy/adoption/">',
                untranslated,
            )
            self.assertNotIn("translation-switcher", untranslated)
            self.assertIn(
                '<link rel="canonical" href="https://templates.moukaeritai.work/">',
                home,
            )

    def test_missing_generated_translation_page_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            site.mkdir()
            map_path = self.prepare_site(site)
            (site / "ja/policy/cli/index.html").unlink()

            with self.assertRaisesRegex(
                TranslationReaderError,
                "references missing generated page",
            ):
                finalize(site, map_path, "https://templates.moukaeritai.work/")

    def test_translation_destination_must_mirror_language_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            site.mkdir()
            map_path = self.prepare_site(site)
            mapping = json.loads(map_path.read_text(encoding="utf-8"))
            mapping["translations"][0]["translation_destination"] = "jp/policy/cli.md"
            map_path.write_text(json.dumps(mapping), encoding="utf-8")

            with self.assertRaisesRegex(
                TranslationReaderError,
                "translation_destination must be ja/policy/cli.md",
            ):
                finalize(site, map_path, "https://templates.moukaeritai.work/")

    def test_translation_map_version_and_canonical_language_are_strict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            site.mkdir()
            map_path = self.prepare_site(site)
            original = json.loads(map_path.read_text(encoding="utf-8"))

            for field, value, message in (
                ("schema_version", 2, "schema_version must be integer 1"),
                ("canonical_language", "fr", "canonical_language must be en"),
            ):
                with self.subTest(field=field):
                    mapping = dict(original)
                    mapping[field] = value
                    map_path.write_text(json.dumps(mapping), encoding="utf-8")
                    with self.assertRaisesRegex(TranslationReaderError, message):
                        finalize(site, map_path, "https://templates.moukaeritai.work/")

    def test_translation_map_reports_missing_and_unsupported_fields_distinctly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            site.mkdir()
            map_path = self.prepare_site(site)
            mapping = json.loads(map_path.read_text(encoding="utf-8"))
            del mapping["canonical_language"]
            map_path.write_text(json.dumps(mapping), encoding="utf-8")
            with self.assertRaisesRegex(
                TranslationReaderError,
                "missing required fields: canonical_language",
            ):
                finalize(site, map_path, "https://templates.moukaeritai.work/")

            mapping["canonical_language"] = "en"
            mapping["extra"] = True
            map_path.write_text(json.dumps(mapping), encoding="utf-8")
            with self.assertRaisesRegex(
                TranslationReaderError,
                "unsupported fields: extra",
            ):
                finalize(site, map_path, "https://templates.moukaeritai.work/")

    def test_page_without_heading_is_rejected_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            site.mkdir()
            map_path = self.prepare_site(site)
            translation = site / "ja/policy/cli/index.html"
            translation.write_text(
                HTML.format(title="CLI", body="日本語").replace(
                    '<h1 id="title">CLI</h1>',
                    '<p id="title">CLI</p>',
                ),
                encoding="utf-8",
            )
            before = (site / "policy/cli/index.html").read_bytes()

            with self.assertRaisesRegex(
                TranslationReaderError,
                "unable to find top-level reader heading",
            ):
                finalize(site, map_path, "https://templates.moukaeritai.work/")
            self.assertEqual(
                (site / "policy/cli/index.html").read_bytes(),
                before,
            )

    def test_html_language_replacement_ignores_attribute_value_text(self) -> None:
        path = Path("page.html")
        source = "<html data-config='contains lang=wrong' lang='en' class=app><head></head>"
        rendered = replace_html_language(source, "ja", path)
        self.assertIn("data-config='contains lang=wrong'", rendered)
        self.assertIn('lang="ja"', rendered)
        self.assertNotIn("lang='en'", rendered)

    def test_html_language_is_inserted_before_trailing_space(self) -> None:
        path = Path("page.html")
        source = '<html class="app" ><head></head>'
        rendered = replace_html_language(source, "fr", path)
        self.assertTrue(rendered.startswith('<html class="app" lang="fr" >'))

    def test_self_closing_html_start_tag_is_rejected(self) -> None:
        with self.assertRaisesRegex(TranslationReaderError, "must not be self-closing"):
            replace_html_language("<html class=app/><head></head>", "ja", Path("page.html"))

    def test_html_language_requires_exactly_one_html_start_tag(self) -> None:
        for source, count in (
            ("<head></head>", 0),
            ("<html><head></head><html>", 2),
        ):
            with self.subTest(count=count):
                with self.assertRaisesRegex(
                    TranslationReaderError,
                    f"expected exactly one html start tag, found {count}",
                ):
                    replace_html_language(source, "ja", Path("page.html"))

    def test_alternates_require_exactly_one_closing_head_tag(self) -> None:
        for source, count in (
            ("<html><body></body></html>", 0),
            ("<html><head></head></head></html>", 2),
        ):
            with self.subTest(count=count):
                with self.assertRaisesRegex(
                    TranslationReaderError,
                    f"expected exactly one closing head tag, found {count}",
                ):
                    replace_alternates(
                        source,
                        [("en", "https://templates.moukaeritai.work/")],
                        Path("page.html"),
                    )

    def test_write_publication_map_matches_reader_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "translation-publication.json"
            record = TranslationRecord(
                publication="policy",
                language="ja",
                canonical_source=PurePosixPath("docs/cli.md"),
                translation_source=PurePosixPath("translations/ja/docs/cli.md"),
                canonical_destination=PurePosixPath("policy/cli.md"),
                translation_destination=PurePosixPath("ja/policy/cli.md"),
                source_file=Path("translation.md"),
            )

            write_publication_map(path, [record])

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
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
                },
            )


if __name__ == "__main__":
    unittest.main()

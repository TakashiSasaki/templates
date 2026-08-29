from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_translation_pairs import (
    TranslationPairValidationError,
    validate,
)


BASE = "https://templates.moukaeritai.work/"


def render_page(
    *,
    language: str,
    canonical_url: str,
    alternates: dict[str, str],
    switcher_links: dict[str, str],
) -> str:
    alternate_markup = "\n".join(
        f'<link rel="alternate" hreflang="{lang}" href="{href}">'
        for lang, href in alternates.items()
    )
    switcher_markup = "".join(
        f'<a class="translation-switcher__link" href="{href}" '
        f'hreflang="{lang}">{lang}</a>'
        for lang, href in switcher_links.items()
    )
    return f"""<!doctype html>
<html lang="{language}">
<head>
<link rel="canonical" href="{canonical_url}">
{alternate_markup}
</head>
<body>
<main>
<h1>Page</h1>
<div class="translation-switcher" role="group">{switcher_markup}</div>
</main>
</body>
</html>
"""


class TranslationPairValidationTests(unittest.TestCase):
    def prepare_pair(
        self,
        root: Path,
        *,
        canonical_destination: str = "policy/index.md",
        translation_destination: str = "ja/policy/index.md",
        canonical_url: str = f"{BASE}policy/",
        translation_url: str = f"{BASE}ja/policy/",
        canonical_switcher_url: str | None = None,
        translation_switcher_url: str | None = None,
        canonical_alternate_url: str | None = None,
        translation_alternate_url: str | None = None,
        canonical_language: str = "en",
        translation_language: str = "ja",
    ) -> tuple[Path, Path]:
        site = root / "site"
        canonical = site / "policy/index.html"
        translated = site / "ja/policy/index.html"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        translated.parent.mkdir(parents=True, exist_ok=True)

        canonical_switcher_url = canonical_switcher_url or translation_url
        translation_switcher_url = translation_switcher_url or canonical_url
        canonical_alternate_url = canonical_alternate_url or translation_url
        translation_alternate_url = translation_alternate_url or translation_url

        alternates = {
            canonical_language: canonical_url,
            translation_language: canonical_alternate_url,
        }
        canonical.write_text(
            render_page(
                language=canonical_language,
                canonical_url=canonical_url,
                alternates=alternates,
                switcher_links={translation_language: canonical_switcher_url},
            ),
            encoding="utf-8",
        )
        translated.write_text(
            render_page(
                language=translation_language,
                canonical_url=canonical_url,
                alternates={
                    canonical_language: canonical_url,
                    translation_language: translation_alternate_url,
                },
                switcher_links={canonical_language: translation_switcher_url},
            ),
            encoding="utf-8",
        )

        mapping = root / "translation-publication.json"
        mapping.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "canonical_language": canonical_language,
                    "translations": [
                        {
                            "publication": "policy",
                            "language": translation_language,
                            "canonical_destination": canonical_destination,
                            "translation_destination": translation_destination,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return site, mapping

    def test_valid_index_pair_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site, mapping = self.prepare_pair(Path(directory))

            self.assertEqual(validate(site, mapping, BASE), (1, 1))

    def test_canonical_switcher_cannot_point_back_to_canonical_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site, mapping = self.prepare_pair(
                Path(directory),
                canonical_switcher_url=f"{BASE}policy/",
            )

            with self.assertRaisesRegex(
                TranslationPairValidationError,
                "translation switcher links",
            ):
                validate(site, mapping, BASE)

    def test_translation_switcher_must_return_to_its_canonical_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site, mapping = self.prepare_pair(
                Path(directory),
                translation_switcher_url=f"{BASE}policy/cli/",
            )

            with self.assertRaisesRegex(
                TranslationPairValidationError,
                "translation switcher links",
            ):
                validate(site, mapping, BASE)

    def test_alternate_url_must_match_the_same_translation_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site, mapping = self.prepare_pair(
                Path(directory),
                canonical_alternate_url=f"{BASE}ja/policy/cli/",
            )

            with self.assertRaisesRegex(
                TranslationPairValidationError,
                "alternates are",
            ):
                validate(site, mapping, BASE)

    def test_malformed_alternate_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site, mapping = self.prepare_pair(Path(directory))
            canonical = site / "policy/index.html"
            canonical.write_text(
                canonical.read_text(encoding="utf-8").replace(
                    f'<link rel="alternate" hreflang="ja" href="{BASE}ja/policy/">',
                    f'<link rel="alternate" href="{BASE}ja/policy/">',
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                TranslationPairValidationError,
                "alternate link requires one href and one hreflang",
            ):
                validate(site, mapping, BASE)

    def test_missing_generated_translation_page_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site, mapping = self.prepare_pair(Path(directory))
            (site / "ja/policy/index.html").unlink()

            with self.assertRaisesRegex(
                TranslationPairValidationError,
                "expected generated translation-pair page is missing",
            ):
                validate(site, mapping, BASE)

    def test_switcher_without_current_publication_mapping_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site, mapping = self.prepare_pair(root)
            extra = site / "policy/untranslated/index.html"
            extra.parent.mkdir(parents=True)
            extra.write_text(
                render_page(
                    language="en",
                    canonical_url=f"{BASE}policy/untranslated/",
                    alternates={},
                    switcher_links={"ja": f"{BASE}ja/policy/untranslated/"},
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                TranslationPairValidationError,
                "without a current translation-publication mapping",
            ):
                validate(site, mapping, BASE)

    def test_auxiliary_generated_surfaces_are_not_reader_switcher_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site, mapping = self.prepare_pair(root)
            for relative in (
                "files/site/content/example/index.html",
                "repository-trees/previews/site/example/index.html",
                "guided/policy/index.html",
                "ja/guided/policy/index.html",
            ):
                page = site / relative
                page.parent.mkdir(parents=True, exist_ok=True)
                page.write_text(
                    render_page(
                        language="ja" if relative.startswith("ja/") else "en",
                        canonical_url=f"{BASE}{relative.removesuffix('index.html')}",
                        alternates={},
                        switcher_links={"ja": f"{BASE}ja/unrelated/"},
                    ),
                    encoding="utf-8",
                )

            self.assertEqual(validate(site, mapping, BASE), (1, 1))

    def test_translation_destination_must_mirror_canonical_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site, mapping = self.prepare_pair(
                Path(directory),
                translation_destination="ja/policy/other.md",
            )

            with self.assertRaisesRegex(
                TranslationPairValidationError,
                "translation_destination must be ja/policy/index.md",
            ):
                validate(site, mapping, BASE)

    def test_html_language_must_match_page_language(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site, mapping = self.prepare_pair(Path(directory))
            translated = site / "ja/policy/index.html"
            translated.write_text(
                translated.read_text(encoding="utf-8").replace(
                    '<html lang="ja">',
                    '<html lang="en">',
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                TranslationPairValidationError,
                "html lang is 'en', expected 'ja'",
            ):
                validate(site, mapping, BASE)

    def test_multiple_languages_require_complete_switcher_and_alternate_sets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            canonical = site / "policy/cli/index.html"
            japanese = site / "ja/policy/cli/index.html"
            french = site / "fr/policy/cli/index.html"
            for page in (canonical, japanese, french):
                page.parent.mkdir(parents=True, exist_ok=True)

            canonical_url = f"{BASE}policy/cli/"
            japanese_url = f"{BASE}ja/policy/cli/"
            french_url = f"{BASE}fr/policy/cli/"
            alternates = {
                "en": canonical_url,
                "fr": french_url,
                "ja": japanese_url,
            }
            canonical.write_text(
                render_page(
                    language="en",
                    canonical_url=canonical_url,
                    alternates=alternates,
                    switcher_links={"fr": french_url, "ja": japanese_url},
                ),
                encoding="utf-8",
            )
            japanese.write_text(
                render_page(
                    language="ja",
                    canonical_url=canonical_url,
                    alternates=alternates,
                    switcher_links={"en": canonical_url},
                ),
                encoding="utf-8",
            )
            french.write_text(
                render_page(
                    language="fr",
                    canonical_url=canonical_url,
                    alternates=alternates,
                    switcher_links={"en": canonical_url},
                ),
                encoding="utf-8",
            )
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
                            },
                            {
                                "publication": "policy",
                                "language": "fr",
                                "canonical_destination": "policy/cli.md",
                                "translation_destination": "fr/policy/cli.md",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(validate(site, mapping, BASE), (1, 2))

    def test_nested_non_index_destination_uses_directory_reader_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            canonical = site / "policy/nested/guide/index.html"
            translated = site / "ja/policy/nested/guide/index.html"
            canonical.parent.mkdir(parents=True, exist_ok=True)
            translated.parent.mkdir(parents=True, exist_ok=True)
            canonical_url = f"{BASE}policy/nested/guide/"
            translated_url = f"{BASE}ja/policy/nested/guide/"
            alternates = {"en": canonical_url, "ja": translated_url}
            canonical.write_text(
                render_page(
                    language="en",
                    canonical_url=canonical_url,
                    alternates=alternates,
                    switcher_links={"ja": translated_url},
                ),
                encoding="utf-8",
            )
            translated.write_text(
                render_page(
                    language="ja",
                    canonical_url=canonical_url,
                    alternates=alternates,
                    switcher_links={"en": canonical_url},
                ),
                encoding="utf-8",
            )
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
                                "canonical_destination": "policy/nested/guide.md",
                                "translation_destination": "ja/policy/nested/guide.md",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(validate(site, mapping, BASE), (1, 1))


if __name__ == "__main__":
    unittest.main()

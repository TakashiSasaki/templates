from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from scripts.translation_link_selection import (
    TranslationLinkSelectionError,
    reader_route,
    rewrite_current_localized_links,
)


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RouteRecord:
    language: str
    canonical_destination: PurePosixPath
    translation_destination: PurePosixPath


def record(language: str, canonical: str, translation: str) -> RouteRecord:
    return RouteRecord(
        language=language,
        canonical_destination=PurePosixPath(canonical),
        translation_destination=PurePosixPath(translation),
    )


class TranslationLinkSelectionTests(unittest.TestCase):
    def test_reader_route_uses_directory_style_urls(self) -> None:
        self.assertEqual(reader_route(PurePosixPath("index.md")), "/")
        self.assertEqual(
            reader_route(PurePosixPath("composition/index.md")),
            "/composition/",
        )
        self.assertEqual(
            reader_route(PurePosixPath("policy/cli.md")),
            "/policy/cli/",
        )
        with self.assertRaisesRegex(
            TranslationLinkSelectionError,
            "reader destination must be Markdown",
        ):
            reader_route(PurePosixPath("assets/example.json"))

    def test_current_cross_publication_links_select_localized_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory) / "docs"
            (docs / "ja" / "composition").mkdir(parents=True)
            (docs / "ja" / "policy").mkdir(parents=True)
            source = docs / "ja" / "index.md"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                "# 日本語\n\n"
                "[Composition](/composition/?mode=reader#top)\n"
                "[No slash](/composition)\n"
                "[Missing](/skill/)\n"
                "![Image](/composition/)\n"
                "[Reference][composition]\n"
                "[composition]: /composition/\n"
                '<a href="/policy/">Policy</a>\n'
                '<a href="/ja/composition/">Already localized</a>\n'
                "```html\n"
                '<a href="/composition/">Code sample</a>\n'
                "```\n",
                encoding="utf-8",
            )
            (docs / "ja" / "composition" / "index.md").write_text(
                "# Composition JA\n",
                encoding="utf-8",
            )
            (docs / "ja" / "policy" / "index.md").write_text(
                "# Policy JA\n",
                encoding="utf-8",
            )
            records = [
                record("ja", "index.md", "ja/index.md"),
                record(
                    "ja",
                    "composition/index.md",
                    "ja/composition/index.md",
                ),
                record("ja", "policy/index.md", "ja/policy/index.md"),
            ]

            changed = rewrite_current_localized_links(records, docs)
            rendered = source.read_text(encoding="utf-8")

            self.assertEqual(changed, 4)
            self.assertIn(
                "[Composition](/ja/composition/?mode=reader#top)",
                rendered,
            )
            self.assertIn("[No slash](/ja/composition/)", rendered)
            self.assertIn("[Missing](/skill/)", rendered)
            self.assertIn("![Image](/composition/)", rendered)
            self.assertIn("[composition]: /ja/composition/", rendered)
            self.assertIn('<a href="/ja/policy/">Policy</a>', rendered)
            self.assertIn(
                '<a href="/ja/composition/">Already localized</a>',
                rendered,
            )
            self.assertIn('<a href="/composition/">Code sample</a>', rendered)

    def test_missing_or_stale_target_remains_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory) / "docs"
            source = docs / "ja" / "index.md"
            source.parent.mkdir(parents=True)
            source.write_text(
                "# 日本語\n\n[Composition](/composition/)\n",
                encoding="utf-8",
            )

            changed = rewrite_current_localized_links(
                [record("ja", "index.md", "ja/index.md")],
                docs,
            )

            self.assertEqual(changed, 0)
            self.assertIn(
                "[Composition](/composition/)",
                source.read_text(encoding="utf-8"),
            )

    def test_translation_availability_is_language_specific(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory) / "docs"
            japanese = docs / "ja" / "index.md"
            french_target = docs / "fr" / "composition" / "index.md"
            japanese.parent.mkdir(parents=True)
            french_target.parent.mkdir(parents=True)
            japanese.write_text(
                "# 日本語\n\n[Composition](/composition/)\n",
                encoding="utf-8",
            )
            french_target.write_text("# Composition FR\n", encoding="utf-8")

            changed = rewrite_current_localized_links(
                [
                    record("ja", "index.md", "ja/index.md"),
                    record(
                        "fr",
                        "composition/index.md",
                        "fr/composition/index.md",
                    ),
                ],
                docs,
            )

            self.assertEqual(changed, 0)
            self.assertIn(
                "[Composition](/composition/)",
                japanese.read_text(encoding="utf-8"),
            )

    def test_conflicting_current_route_mapping_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory) / "docs"
            docs.mkdir()
            records = [
                record("ja", "policy/cli.md", "ja/policy/cli.md"),
                record("ja", "policy/cli.md", "ja/policy/cli-v2.md"),
            ]

            with self.assertRaisesRegex(
                TranslationLinkSelectionError,
                "conflicting localized route",
            ):
                rewrite_current_localized_links(records, docs)

    def test_translation_destination_must_remain_inside_docs_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            docs = base / "docs"
            docs.mkdir()
            outside = base / "outside.md"
            outside.write_text("# outside\n", encoding="utf-8")

            with self.assertRaisesRegex(
                TranslationLinkSelectionError,
                "published translation escapes documentation root",
            ):
                rewrite_current_localized_links(
                    [record("ja", "index.md", "../outside.md")],
                    docs,
                )

    def test_published_translation_must_exist_as_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory) / "docs"
            docs.mkdir()

            with self.assertRaisesRegex(
                TranslationLinkSelectionError,
                "published translation must be a regular file",
            ):
                rewrite_current_localized_links(
                    [record("ja", "index.md", "ja/index.md")],
                    docs,
                )

    def test_site_translation_sources_keep_cross_authority_routes_canonical(self) -> None:
        landing = (ROOT / "translations" / "ja" / "docs" / "landing.md").read_text(
            encoding="utf-8"
        )
        lifecycle = (
            ROOT / "translations" / "ja" / "docs" / "lifecycle.md"
        ).read_text(encoding="utf-8")

        self.assertIn('href="/composition/"', landing)
        self.assertIn('href="/policy/"', landing)
        self.assertNotIn('href="/ja/composition/"', landing)
        self.assertNotIn('href="/ja/policy/"', landing)
        self.assertIn("[Composition state](/lifecycle/composition-state/)", lifecycle)
        self.assertNotIn("/ja/lifecycle/composition-state/", lifecycle)


if __name__ == "__main__":
    unittest.main()

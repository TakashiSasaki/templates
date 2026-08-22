from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from scripts.publish_translations import TranslationRecord
from scripts.reader_navigation_locales import (
    ReaderNavigationLocaleError,
    build_runtime_map,
    load_overlays,
)


class ReaderNavigationLocaleTests(unittest.TestCase):
    def navigation(self) -> list[dict[str, object]]:
        return [
            {
                "title": "Home",
                "publication": "site",
                "document": "home",
                "destination": PurePosixPath("index.md"),
            },
            {
                "title": "Composition",
                "children": [
                    {
                        "title": "Overview",
                        "publication": "composition",
                        "document": "overview",
                        "destination": PurePosixPath("composition/index.md"),
                    },
                    {
                        "title": "Architecture",
                        "children": [
                            {
                                "title": "Composition model",
                                "publication": "composition",
                                "document": "model",
                                "destination": PurePosixPath(
                                    "composition/architecture/composition-model.md"
                                ),
                            }
                        ],
                    },
                ],
            },
            {
                "title": "Repository trees",
                "children": [
                    {
                        "title": "Overview",
                        "publication": "site",
                        "document": "trees",
                        "destination": PurePosixPath("repository-trees/index.md"),
                    }
                ],
            },
        ]

    def write_overlay(self, path: Path, labels: list[dict[str, str]]) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "canonical_language": "en",
                    "locales": [{"language": "ja", "labels": labels}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def complete_labels(self) -> list[dict[str, str]]:
        return [
            {"id": "home", "canonical": "Home", "localized": "ホーム"},
            {
                "id": "composition",
                "canonical": "Composition",
                "localized": "Composition",
            },
            {"id": "overview", "canonical": "Overview", "localized": "概要"},
            {
                "id": "architecture",
                "canonical": "Architecture",
                "localized": "アーキテクチャ",
            },
            {
                "id": "composition-model",
                "canonical": "Composition model",
                "localized": "Composition モデル",
            },
            {
                "id": "repository-trees",
                "canonical": "Repository trees",
                "localized": "リポジトリツリー",
            },
        ]

    def record(
        self,
        canonical: str,
        translation: str,
        *,
        language: str = "ja",
    ) -> TranslationRecord:
        return TranslationRecord(
            publication="composition",
            language=language,
            canonical_source=PurePosixPath("README.md"),
            translation_source=PurePosixPath("translations/ja/README.md"),
            canonical_destination=PurePosixPath(canonical),
            translation_destination=PurePosixPath(translation),
            source_file=Path("translation.md"),
        )

    def test_overlay_must_exactly_cover_prepared_navigation_titles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            labels = self.complete_labels()
            labels.pop()
            self.write_overlay(path, labels)

            with self.assertRaisesRegex(
                ReaderNavigationLocaleError,
                "must exactly cover canonical navigation titles",
            ):
                load_overlays(path, self.navigation())

    def test_duplicate_canonical_titles_share_one_localized_label(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            self.write_overlay(path, self.complete_labels())

            overlays = load_overlays(path, self.navigation())

            self.assertEqual(overlays["ja"]["Overview"], "概要")
            self.assertEqual(len(overlays["ja"]), 6)

    def test_runtime_routes_include_only_current_translation_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locales.json"
            self.write_overlay(path, self.complete_labels())
            overlays = load_overlays(path, self.navigation())

            runtime = build_runtime_map(
                overlays,
                [
                    self.record(
                        "composition/index.md",
                        "ja/composition/index.md",
                    ),
                    self.record(
                        "composition/architecture/composition-model.md",
                        "ja/composition/architecture/composition-model.md",
                    ),
                    self.record(
                        "policy/index.md",
                        "fr/policy/index.md",
                        language="fr",
                    ),
                ],
            )

            locale = runtime["locales"][0]
            self.assertEqual(locale["language"], "ja")
            self.assertEqual(
                locale["routes"],
                {
                    "/composition/": "/ja/composition/",
                    "/composition/architecture/composition-model/": (
                        "/ja/composition/architecture/composition-model/"
                    ),
                },
            )
            self.assertNotIn("/policy/", locale["routes"])

    def test_runtime_route_conflicts_fail_closed(self) -> None:
        overlays = {"ja": {"Home": "ホーム"}}
        with self.assertRaisesRegex(
            ReaderNavigationLocaleError,
            "conflicting localized route",
        ):
            build_runtime_map(
                overlays,
                [
                    self.record("composition/index.md", "ja/composition/index.md"),
                    self.record("composition/index.md", "ja/other/index.md"),
                ],
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_index_navigation_locale_viewer import (
    LocaleViewerError,
    load_overlays,
    locale_index_path,
    locale_index_url,
    render_localized_index,
    render_localized_landing,
    translated_edge_href,
)

REPOSITORY = "TakashiSasaki/templates"
REVISION = "a" * 40


class IndexNavigationLocaleViewerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = {"name": "policy", "revision": REVISION}

    def test_index_target_uses_localized_guided_route_only_when_overlay_exists(self) -> None:
        edge = {
            "kind": "index",
            "target": "docs/provider/index.md",
            "fragment": None,
            "source": "docs/index.md",
            "line": 5,
            "raw_target": "provider/index.md",
        }
        href, route_kind, external = translated_edge_href(
            "ja",
            REPOSITORY,
            self.provider,
            edge,
            {},
            {"docs/provider/index.md": {}},
            {},
        )
        self.assertEqual(
            locale_index_url("ja", "policy", "docs/provider/index.md"), href
        )
        self.assertEqual("index", route_kind)
        self.assertFalse(external)

    def test_published_reader_target_uses_matching_reader_translation(self) -> None:
        edge = {
            "kind": "file",
            "target": "docs/overview.md",
            "fragment": None,
            "source": "docs/index.md",
            "line": 5,
            "raw_target": "overview.md",
        }
        href, route_kind, external = translated_edge_href(
            "ja",
            REPOSITORY,
            self.provider,
            edge,
            {"docs/overview.md": "policy/index.md"},
            {},
            {("ja", "policy", "policy/index.md"): "ja/policy/index.md"},
        )
        self.assertEqual("/ja/policy/", href)
        self.assertEqual("published document", route_kind)
        self.assertFalse(external)

    def test_published_reader_fragment_falls_back_to_canonical_reader(self) -> None:
        edge = {
            "kind": "file",
            "target": "docs/overview.md",
            "fragment": "scope",
            "source": "docs/index.md",
            "line": 5,
            "raw_target": "overview.md#scope",
        }
        href, route_kind, external = translated_edge_href(
            "ja",
            REPOSITORY,
            self.provider,
            edge,
            {"docs/overview.md": "policy/index.md"},
            {},
            {("ja", "policy", "policy/index.md"): "ja/policy/index.md"},
        )
        self.assertEqual("/policy/#scope", href)
        self.assertEqual("published document", route_kind)
        self.assertFalse(external)

    def test_missing_reader_translation_falls_back_to_canonical_reader(self) -> None:
        edge = {
            "kind": "file",
            "target": "docs/overview.md",
            "fragment": None,
            "source": "docs/index.md",
            "line": 5,
            "raw_target": "overview.md",
        }
        href, route_kind, external = translated_edge_href(
            "ja",
            REPOSITORY,
            self.provider,
            edge,
            {"docs/overview.md": "policy/index.md"},
            {},
            {},
        )
        self.assertEqual("/policy/", href)
        self.assertEqual("published document", route_kind)
        self.assertFalse(external)

    def test_japanese_landing_reuses_canonical_machine_readable_graph(self) -> None:
        graph = {
            "providers": [
                {
                    "name": name,
                    "revision": REVISION,
                    "diagnostics": {
                        "index_count": 1,
                        "edge_count": 2,
                        "max_index_depth": 0,
                    },
                }
                for name in ("skill", "policy", "webapp")
            ]
        }
        locale = {
            "policy": {
                "docs/index.md": {
                    "title": "ポリシーナビゲーション",
                    "sections": [],
                    "links": [],
                }
            }
        }
        source = render_localized_landing("ja", graph, locale)
        self.assertIn("インデックスに沿った文書探索", source)
        self.assertIn('/guided/graph.json', source)
        self.assertNotIn('/ja/guided/graph.json', source)
        self.assertIn('/ja/guided/policy/', source)
        self.assertIn('/guided/skill/', source)

    def test_three_letter_language_starting_with_ja_is_not_japanese(self) -> None:
        graph = {
            "providers": [
                {
                    "name": name,
                    "revision": REVISION,
                    "diagnostics": {
                        "index_count": 1,
                        "edge_count": 0,
                        "max_index_depth": 0,
                    },
                }
                for name in ("skill", "policy", "webapp")
            ]
        }
        source = render_localized_landing("jam", graph, {})
        self.assertIn("Index-guided document discovery", source)
        self.assertIn("Page path:", source)
        self.assertNotIn("インデックスに沿った文書探索", source)
        self.assertNotIn("ページパス:", source)

    def test_unsafe_language_cannot_become_filesystem_component(self) -> None:
        with self.assertRaisesRegex(LocaleViewerError, "language tag"):
            locale_index_path("../escape", "policy", "docs/index.md")
        with self.assertRaisesRegex(LocaleViewerError, "language tag"):
            locale_index_url("/tmp", "policy", "docs/index.md")

    def test_overlay_loader_rejects_unsafe_language(self) -> None:
        graph = {"schema_version": 1, "providers": []}
        payload = {
            "schema_version": 1,
            "canonical_graph_schema_version": 1,
            "canonical_language": "en",
            "locales": [{"language": "../escape", "providers": []}],
        }
        with tempfile.TemporaryDirectory(prefix="guided-overlay-") as directory:
            path = Path(directory) / "overlay.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(LocaleViewerError, "language tag"):
                load_overlays(path, graph)

    def test_overlay_loader_rejects_graph_schema_mismatch(self) -> None:
        graph = {"schema_version": 1, "providers": []}
        payload = {
            "schema_version": 1,
            "canonical_graph_schema_version": 2,
            "canonical_language": "en",
            "locales": [],
        }
        with tempfile.TemporaryDirectory(prefix="guided-overlay-") as directory:
            path = Path(directory) / "overlay.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(LocaleViewerError, "does not match graph schema"):
                load_overlays(path, graph)

    def test_overlay_loader_rejects_provider_revision_mismatch(self) -> None:
        graph = {
            "schema_version": 1,
            "providers": [
                {
                    "name": "policy",
                    "revision": REVISION,
                    "indexes": [],
                    "edges": [],
                }
            ],
        }
        payload = {
            "schema_version": 1,
            "canonical_graph_schema_version": 1,
            "canonical_language": "en",
            "locales": [
                {
                    "language": "ja",
                    "providers": [
                        {
                            "name": "policy",
                            "revision": "b" * 40,
                            "indexes": [],
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory(prefix="guided-overlay-") as directory:
            path = Path(directory) / "overlay.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(LocaleViewerError, "revision mismatch"):
                load_overlays(path, graph)

    def test_localized_headings_preserve_canonical_fragment_ids(self) -> None:
        canonical_index = {
            "path": "docs/index.md",
            "title": "Policy navigation",
            "sections": [{"title": "Details", "level": 2}],
        }
        overlay = {
            "title": "ポリシーナビゲーション",
            "sections": [{"title": "詳細", "level": 2}],
            "links": [],
        }
        provider = {
            "name": "policy",
            "revision": REVISION,
        }
        source = render_localized_index(
            "ja",
            REPOSITORY,
            provider,
            canonical_index,
            overlay,
            {"docs/index.md": overlay},
            {},
            {},
            {"docs/index.md": canonical_index},
            {},
            [],
        )
        self.assertIn('<h1 id="policy-navigation">ポリシーナビゲーション</h1>', source)
        self.assertIn('<h2 id="details">詳細</h2>', source)
        self.assertNotIn('id="ポリシーナビゲーション"', source)


if __name__ == "__main__":
    unittest.main()

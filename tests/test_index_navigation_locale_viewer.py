from __future__ import annotations

import unittest

from scripts.generate_index_navigation_locale_viewer import (
    locale_index_url,
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


if __name__ == "__main__":
    unittest.main()

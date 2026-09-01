from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.prepare_repository_tree_publication import augment_manifest
from scripts.reader_navigation_locales import load_overlays


ROOT = Path(__file__).resolve().parents[1]


class ReaderNavigationLocaleInventoryTests(unittest.TestCase):
    def test_japanese_overlay_exactly_covers_prepared_site_navigation(self) -> None:
        manifest = json.loads(
            (ROOT / "site-manifest.json").read_text(encoding="utf-8")
        )
        prepared = augment_manifest(manifest)

        overlays = load_overlays(
            ROOT / "reader-navigation-locales.json",
            prepared["navigation"],
        )

        self.assertEqual(set(overlays), {"ja"})
        japanese = overlays["ja"]
        self.assertEqual(japanese["Documentation portal"], "ドキュメントポータル")
        self.assertEqual(japanese["Repository trees"], "リポジトリツリー")
        self.assertEqual(japanese["Composition model"], "Composition モデル")
        self.assertEqual(japanese["Publication boundary"], "公開境界")
        self.assertEqual(japanese["Web"], "Web")
        self.assertEqual(
            japanese["Choose Website or Web application"],
            "Website と Web application を選ぶ",
        )
        self.assertEqual(japanese["Website"], "Website")
        self.assertEqual(japanese["Web application"], "Web application")
        self.assertEqual(japanese["Reusable capabilities"], "再利用可能な capability")
        self.assertEqual(japanese["Routes v3 to v4"], "Routes v3 → v4")
        self.assertEqual(japanese["PWA offline v1 to v2"], "PWA offline v1 → v2")
        self.assertEqual(japanese["PWA update v1 to v2"], "PWA update v1 → v2")


if __name__ == "__main__":
    unittest.main()

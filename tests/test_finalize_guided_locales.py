from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_guided_locales import (
    GuidedLocaleFinalizeError,
    finalize,
)


def page(title: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<link rel="canonical" href="https://templates.moukaeritai.work/">'
        f'<title>{title}</title></head><body><main><h1>{title}</h1></main></body></html>'
    )


class FinalizeGuidedLocalesTests(unittest.TestCase):
    def test_paired_pages_receive_canonical_language_and_switcher_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guided-locale-") as directory:
            root = Path(directory)
            canonical = root / "guided" / "policy" / "index.html"
            translated = root / "ja" / "guided" / "policy" / "index.html"
            canonical.parent.mkdir(parents=True)
            translated.parent.mkdir(parents=True)
            canonical.write_text(page("Policy navigation"), encoding="utf-8")
            translated.write_text(page("ポリシーナビゲーション"), encoding="utf-8")
            pair_map = root / "pairs.json"
            pair_map.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "canonical_language": "en",
                        "pages": [
                            {
                                "language": "ja",
                                "canonical_path": "guided/policy/index.html",
                                "translation_path": "ja/guided/policy/index.html",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            finalize(root, pair_map, "https://templates.moukaeritai.work/")
            english = canonical.read_text(encoding="utf-8")
            japanese = translated.read_text(encoding="utf-8")

            self.assertIn('href="https://templates.moukaeritai.work/guided/policy/"', english)
            self.assertIn('hreflang="ja"', english)
            self.assertIn('Site · Canonical English', english)
            self.assertIn('>日本語</a>', english)
            self.assertIn('lang="ja"', japanese)
            self.assertIn('href="https://templates.moukaeritai.work/guided/policy/"', japanese)
            self.assertNotIn('rel="canonical" href="https://templates.moukaeritai.work/ja/guided/policy/"', japanese)
            self.assertIn('Site · 日本語参考表示', japanese)
            self.assertIn('English · Canonical', japanese)
            self.assertIn('rel="manifest" href="/app.webmanifest"', japanese)
            self.assertIn('name="theme-color" content="#3f51b5"', japanese)

    def test_non_mirrored_localized_path_is_rejected_before_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guided-locale-") as directory:
            root = Path(directory)
            canonical = root / "guided" / "policy" / "index.html"
            canonical.parent.mkdir(parents=True)
            canonical.write_text(page("Policy navigation"), encoding="utf-8")
            before = canonical.read_bytes()
            pair_map = root / "pairs.json"
            pair_map.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "canonical_language": "en",
                        "pages": [
                            {
                                "language": "ja",
                                "canonical_path": "guided/policy/index.html",
                                "translation_path": "ja/guided/other/index.html",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(GuidedLocaleFinalizeError, "must mirror"):
                finalize(root, pair_map, "https://templates.moukaeritai.work/")
            self.assertEqual(before, canonical.read_bytes())


if __name__ == "__main__":
    unittest.main()

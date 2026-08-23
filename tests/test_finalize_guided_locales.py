from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from finalize_guided_locales import (  # noqa: E402
    GuidedLocaleFinalizeError,
    finalize,
)

REVISION = "a" * 40


def page(title: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; style-src \'unsafe-inline\'; '
        'manifest-src \'self\'; base-uri \'none\'; form-action \'none\'">'
        '<link rel="canonical" href="https://templates.moukaeritai.work/">'
        f'<title>{title}</title></head><body><main><h1>{title}</h1></main></body></html>'
    )


def guided_page(title: str, page_path: str) -> str:
    source_url = (
        "https://github.com/TakashiSasaki/templates/blob/"
        f"{REVISION}/docs/index.md"
    )
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; style-src \'unsafe-inline\'">'
        '<link rel="canonical" href="https://templates.moukaeritai.work/">'
        f'<title>{title}</title></head><body>'
        f'<p class="page-path"><span class="page-path-label">ページパス:</span> '
        f'<code>{page_path}</code></p>'
        f'<main><h1>{title}</h1>'
        f'<a href="{source_url}" target="_blank" rel="noopener">不変の GitHub ソース</a>'
        '</main></body></html>'
    )


def write_pair_map(root: Path, pages: list[dict[str, str]]) -> Path:
    pair_map = root / "pairs.json"
    pair_map.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "canonical_language": "en",
                "pages": pages,
            }
        ),
        encoding="utf-8",
    )
    return pair_map


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
            pair_map = write_pair_map(
                root,
                [
                    {
                        "language": "ja",
                        "canonical_path": "guided/policy/index.html",
                        "translation_path": "ja/guided/policy/index.html",
                    }
                ],
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
            for source in (english, japanese):
                self.assertIn('<script src="/javascripts/pwa.js" defer></script>', source)
                self.assertIn(
                    '<link rel="stylesheet" href="/stylesheets/freshness-status.css">',
                    source,
                )
                self.assertIn("script-src 'self'", source)
                self.assertIn("style-src 'self' 'unsafe-inline'", source)
                self.assertIn("connect-src 'self'", source)
                self.assertIn("worker-src 'self'", source)
                self.assertIn("manifest-src 'self'", source)

    def test_localized_guided_page_receives_public_and_github_copy_controls(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guided-locale-") as directory:
            root = Path(directory)
            canonical = root / "guided" / "policy" / "index.html"
            translated = root / "ja" / "guided" / "policy" / "index.html"
            canonical.parent.mkdir(parents=True)
            translated.parent.mkdir(parents=True)
            canonical.write_text(page("Policy navigation"), encoding="utf-8")
            translated.write_text(
                guided_page("ポリシーナビゲーション", "/ja/guided/policy/"),
                encoding="utf-8",
            )
            pair_map = write_pair_map(
                root,
                [
                    {
                        "language": "ja",
                        "canonical_path": "guided/policy/index.html",
                        "translation_path": "ja/guided/policy/index.html",
                    }
                ],
            )

            finalize(root, pair_map, "https://templates.moukaeritai.work/")
            japanese = translated.read_text(encoding="utf-8")
            source_url = (
                "https://github.com/TakashiSasaki/templates/blob/"
                f"{REVISION}/docs/index.md"
            )

            self.assertIn('data-copy-name="GitHub URL"', japanese)
            self.assertIn(f'data-copy-url="{source_url}"', japanese)
            self.assertIn('data-copy-name="public URL"', japanese)
            self.assertIn(
                'data-copy-url="https://templates.moukaeritai.work/ja/guided/policy/"',
                japanese,
            )
            self.assertIn('<script src="/javascripts/guided-copy.js" defer></script>', japanese)
            self.assertIn('<script src="/javascripts/pwa.js" defer></script>', japanese)
            self.assertIn("script-src 'self'", japanese)
            self.assertIn("connect-src 'self'", japanese)
            self.assertIn("worker-src 'self'", japanese)
            self.assertIn('<span class="page-path-label">ページパス:</span>', japanese)

    def test_every_translation_receives_complete_alternate_set(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guided-locale-") as directory:
            root = Path(directory)
            canonical = root / "guided" / "policy" / "index.html"
            japanese = root / "ja" / "guided" / "policy" / "index.html"
            french = root / "fr" / "guided" / "policy" / "index.html"
            for path, title in (
                (canonical, "Policy navigation"),
                (japanese, "ポリシーナビゲーション"),
                (french, "Navigation de politique"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(page(title), encoding="utf-8")
            pair_map = write_pair_map(
                root,
                [
                    {
                        "language": "ja",
                        "canonical_path": "guided/policy/index.html",
                        "translation_path": "ja/guided/policy/index.html",
                    },
                    {
                        "language": "fr",
                        "canonical_path": "guided/policy/index.html",
                        "translation_path": "fr/guided/policy/index.html",
                    },
                ],
            )

            finalize(root, pair_map, "https://templates.moukaeritai.work/")
            for path in (canonical, japanese, french):
                source = path.read_text(encoding="utf-8")
                self.assertIn('hreflang="en"', source)
                self.assertIn('hreflang="fr"', source)
                self.assertIn('hreflang="ja"', source)

    def test_metadata_urls_percent_encode_filesystem_path_components(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guided-locale-") as directory:
            root = Path(directory)
            canonical = root / "guided" / "policy" / "a#b" / "index.html"
            translated = root / "ja" / "guided" / "policy" / "a#b" / "index.html"
            canonical.parent.mkdir(parents=True)
            translated.parent.mkdir(parents=True)
            canonical.write_text(page("Encoded path"), encoding="utf-8")
            translated.write_text(page("符号化パス"), encoding="utf-8")
            pair_map = write_pair_map(
                root,
                [
                    {
                        "language": "ja",
                        "canonical_path": "guided/policy/a#b/index.html",
                        "translation_path": "ja/guided/policy/a#b/index.html",
                    }
                ],
            )

            finalize(root, pair_map, "https://templates.moukaeritai.work/")
            for path in (canonical, translated):
                source = path.read_text(encoding="utf-8")
                self.assertIn(
                    'rel="canonical" href="https://templates.moukaeritai.work/guided/policy/a%23b/"',
                    source,
                )
                self.assertNotIn("/guided/policy/a#b/", source)

    def test_non_mirrored_localized_path_is_rejected_before_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guided-locale-") as directory:
            root = Path(directory)
            canonical = root / "guided" / "policy" / "index.html"
            canonical.parent.mkdir(parents=True)
            canonical.write_text(page("Policy navigation"), encoding="utf-8")
            before = canonical.read_bytes()
            pair_map = write_pair_map(
                root,
                [
                    {
                        "language": "ja",
                        "canonical_path": "guided/policy/index.html",
                        "translation_path": "ja/guided/other/index.html",
                    }
                ],
            )
            with self.assertRaisesRegex(GuidedLocaleFinalizeError, "must mirror"):
                finalize(root, pair_map, "https://templates.moukaeritai.work/")
            self.assertEqual(before, canonical.read_bytes())

    def test_unsafe_language_tag_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guided-locale-") as directory:
            root = Path(directory)
            pair_map = write_pair_map(
                root,
                [
                    {
                        "language": "../escape",
                        "canonical_path": "guided/policy/index.html",
                        "translation_path": "ja/guided/policy/index.html",
                    }
                ],
            )
            with self.assertRaisesRegex(GuidedLocaleFinalizeError, "language is invalid"):
                finalize(root, pair_map, "https://templates.moukaeritai.work/")

    def test_cli_executes_real_import_and_finalization_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="guided-locale-") as directory:
            root = Path(directory)
            canonical = root / "guided" / "policy" / "index.html"
            translated = root / "ja" / "guided" / "policy" / "index.html"
            canonical.parent.mkdir(parents=True)
            translated.parent.mkdir(parents=True)
            canonical.write_text(page("Policy navigation"), encoding="utf-8")
            translated.write_text(page("ポリシーナビゲーション"), encoding="utf-8")
            pair_map = write_pair_map(
                root,
                [
                    {
                        "language": "ja",
                        "canonical_path": "guided/policy/index.html",
                        "translation_path": "ja/guided/policy/index.html",
                    }
                ],
            )
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "finalize_guided_locales.py"),
                    "--site-root",
                    str(root),
                    "--pair-map",
                    str(pair_map),
                    "--canonical-url",
                    "https://templates.moukaeritai.work/",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertIn("guided locale group finalized", process.stdout)


if __name__ == "__main__":
    unittest.main()

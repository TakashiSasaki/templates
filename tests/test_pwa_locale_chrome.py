from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_pwa_locale_chrome  # noqa: E402


class PwaLocaleChromeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.client = (ROOT / "assets/javascripts/pwa.js").read_text(encoding="utf-8")
        self.workflow = (ROOT / ".github/workflows/mobile-visual-regression.yml").read_text(
            encoding="utf-8"
        )
        self.checker = (ROOT / "scripts/check_pwa_locale_chrome.py").read_text(
            encoding="utf-8"
        )

    def test_site_chrome_registry_is_shared_by_client_and_worker(self) -> None:
        self.assertIn('const siteChromeLocalesHref = "/site-chrome-locales.json"', self.client)
        self.assertIn('const SITE_CHROME_LOCALES_PATH = "/site-chrome-locales.json"', self.worker)
        self.assertIn('"/site-chrome-locales.json"', self.worker)
        self.assertIn("async function loadSiteChromeLocales()", self.client)
        self.assertIn("async function loadSiteChromeLocales()", self.worker)
        self.assertIn("pwaFreshnessStrings(model", self.client)
        self.assertIn("pwaFreshnessStrings(model", self.worker)

    def test_runtime_does_not_reintroduce_fixed_english_freshness_copy(self) -> None:
        for text in (
            "Saved copy.",
            "Checking for the latest version…",
            "The latest version could not be verified.",
            "Update available.",
            "The published page changed.",
        ):
            with self.subTest(text=text):
                self.assertNotIn(text, self.client)
                self.assertNotIn(text, self.worker)

    def test_worker_localizes_cached_and_cache_miss_fallbacks(self) -> None:
        self.assertIn("const language = htmlLanguage(source)", self.worker)
        self.assertIn("freshnessNoticeHtml(state, strings)", self.worker)
        self.assertIn("async function offlineResponse(request)", self.worker)
        self.assertIn("requestLanguage(model, request)", self.worker)
        self.assertIn("strings?.offline_unavailable", self.worker)

    def test_browser_checker_is_wired_into_mobile_ci(self) -> None:
        self.assertIn("Check localized PWA freshness chrome", self.workflow)
        self.assertIn("python scripts/check_pwa_locale_chrome.py", self.workflow)
        self.assertIn('EXPECTED_JA["update_available"]', self.checker)
        self.assertIn('EXPECTED_JA["unverified"]', self.checker)
        self.assertIn('EXPECTED_JA["offline_unavailable"]', self.checker)
        self.assertIn("EXPECTED_EN_OFFLINE", self.checker)
        self.assertIn('"/de/__pwa-locale-cache-miss__/"', self.checker)
        self.assertIn("arg=DOCUMENT_CACHE_NAME", self.checker)
        self.assertIn('arg=EXPECTED_JA["update_available"]', self.checker)

    def test_checker_fails_before_browser_start_when_assets_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(check_pwa_locale_chrome.PwaLocaleChromeError) as context:
                check_pwa_locale_chrome.run_check(Path(directory), None)
        self.assertIn("built site is missing required PWA locale assets", str(context.exception))


if __name__ == "__main__":
    unittest.main()

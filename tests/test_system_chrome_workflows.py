from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BROWSER_SCRIPTS = (
    ROOT / "scripts/check_composition_playground_browser.py",
    ROOT / "scripts/check_composition_playground_final_browser.py",
    ROOT / "scripts/check_composition_playground_final_grid_browser.py",
    ROOT / "scripts/check_composition_playground_final_three_browser.py",
    ROOT / "scripts/check_composition_playground_latest_five_browser.py",
    ROOT / "scripts/check_composition_playground_cross_authority.py",
    ROOT / "scripts/check_mobile_layout_core.py",
    ROOT / "scripts/check_repository_browser_filter.py",
    ROOT / "scripts/check_glossary_locale_chrome.py",
    ROOT / "scripts/check_pwa_capabilities.py",
    ROOT / "scripts/check_pwa_commit_regressions.py",
    ROOT / "scripts/check_pwa_locale_chrome.py",
    ROOT / "scripts/check_pwa_slow_convergence.py",
    ROOT / "scripts/check_search_history.py",
    ROOT / "scripts/check_search_history_review_regressions.py",
)


class SystemChromeWorkflowTests(unittest.TestCase):
    def test_browser_scripts_select_official_system_chrome_channel(self) -> None:
        for path in BROWSER_SCRIPTS:
            source = path.read_text(encoding="utf-8")
            self.assertIn('playwright.chromium.launch(channel="chrome"', source)
            self.assertNotIn("playwright.chromium.launch()", source)

    def test_browser_workflows_use_system_chrome_except_pwa_lifecycle_jobs(self) -> None:
        workflows = (
            ROOT / ".github/workflows/build-pages.yml",
            ROOT / ".github/workflows/mobile-visual-regression.yml",
            ROOT / ".github/workflows/search-history-regression.yml",
            ROOT / ".github/workflows/site-composition-playground-explain.yml",
            ROOT / ".github/workflows/site-composition-playground-cross-authority.yml",
        )
        for path in workflows:
            source = path.read_text(encoding="utf-8")
            if path.name in {"build-pages.yml", "mobile-visual-regression.yml"}:
                self.assertIn("playwright install", source)
            else:
                self.assertNotIn("playwright install", source)
            self.assertIn("google-chrome --version", source)


if __name__ == "__main__":
    unittest.main()

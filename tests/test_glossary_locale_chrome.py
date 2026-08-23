from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_glossary_locale_chrome  # noqa: E402


class GlossaryLocaleChromeCheckerTests(unittest.TestCase):
    def test_missing_required_assets_fail_closed_before_playwright(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site_root = Path(directory)
            with self.assertRaisesRegex(
                check_glossary_locale_chrome.GlossaryLocaleChromeError,
                "built site is missing required Glossary assets",
            ):
                check_glossary_locale_chrome.run_check(site_root, None)

    def test_mobile_visual_workflow_runs_glossary_locale_checker(self) -> None:
        workflow = (ROOT / ".github/workflows/mobile-visual-regression.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Check localized inline Glossary chrome", workflow)
        self.assertIn("python scripts/check_glossary_locale_chrome.py", workflow)
        self.assertIn(
            "--output build/mobile-visual/glossary-locale-chrome.json",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()

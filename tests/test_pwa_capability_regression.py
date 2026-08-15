from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check_pwa_capabilities.py"
WORKFLOW = ROOT / ".github/workflows/mobile-visual-regression.yml"
sys.path.insert(0, str(ROOT / "scripts"))

import check_pwa_capabilities  # noqa: E402


class PwaCapabilityRegressionTests(unittest.TestCase):
    def test_checker_exercises_live_service_worker_message_contract(self) -> None:
        source = CHECKER.read_text(encoding="utf-8")
        self.assertIn(
            'worker.postMessage({ type: "templates:get-freshness-capabilities" })',
            source,
        )
        self.assertIn('event.data?.type === "templates:freshness-capabilities"', source)
        for state in ("verified-current", "checking", "cached-unverified", "update-available"):
            self.assertIn(f'"{state}"', source)
        self.assertIn('EXPECTED_SITE_VERSION_URL = "/site-version.json"', source)
        self.assertIn(
            'EXPECTED_DOCUMENT_CACHE_NAME = "templates-portal-documents-v1"',
            source,
        )
        self.assertIn('service_workers="allow"', source)
        self.assertIn("}, 5000);", source)

    def test_checker_validates_all_required_install_assets_before_browser_start(self) -> None:
        source = CHECKER.read_text(encoding="utf-8")
        for path in (
            'site_root / "service-worker.js"',
            'site_root / "javascripts/pwa.js"',
            'site_root / "icon.svg"',
            'site_root / "app.webmanifest"',
            'site_root / "stylesheets/freshness-status.css"',
        ):
            with self.subTest(path=path):
                self.assertIn(path, source)

        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(check_pwa_capabilities.PwaCapabilityError) as context:
                check_pwa_capabilities.run_check(Path(temporary_directory), None)
        self.assertIn("built site is missing required PWA assets", str(context.exception))

    def test_mobile_visual_workflow_runs_capability_checker(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Check PWA freshness capability messaging", workflow)
        self.assertIn("python scripts/check_pwa_capabilities.py", workflow)
        self.assertIn("build/mobile-visual/pwa-capabilities.json", workflow)


if __name__ == "__main__":
    unittest.main()

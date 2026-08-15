from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check_pwa_capabilities.py"
WORKFLOW = ROOT / ".github/workflows/mobile-visual-regression.yml"


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

    def test_mobile_visual_workflow_runs_capability_checker(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Check PWA freshness capability messaging", workflow)
        self.assertIn("python scripts/check_pwa_capabilities.py", workflow)
        self.assertIn("build/mobile-visual/pwa-capabilities.json", workflow)


if __name__ == "__main__":
    unittest.main()

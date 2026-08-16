from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check_pwa_capabilities.py"
WORKFLOW = ROOT / ".github/workflows/mobile-visual-regression.yml"
WORKER = ROOT / "assets/service-worker.js"
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
        self.assertIn(
            'EXPECTED_GLOSSARY_CACHE_NAME = "templates-portal-glossary-v1"',
            source,
        )
        self.assertIn(
            'EXPECTED_GLOSSARY_MODEL_URL = "/glossary/index.json"',
            source,
        )
        self.assertIn("EXPECTED_SOFT_TIMEOUT_MS = 1500", source)
        self.assertIn('capabilities.get("glossaryCacheName")', source)
        self.assertIn('capabilities.get("glossaryModelUrl")', source)
        self.assertIn('capabilities.get("softTimeoutMs")', source)
        self.assertIn('capabilities.get("workerInstanceId")', source)
        self.assertIn('not isinstance(worker_instance_id, str) or not worker_instance_id', source)
        self.assertIn('service_workers="allow"', source)
        self.assertIn("}, 5000);", source)

    def test_worker_exposes_glossary_and_slow_network_capabilities_checked_by_browser(self) -> None:
        worker = WORKER.read_text(encoding="utf-8")
        self.assertIn("glossaryCacheName: GLOSSARY_CACHE_NAME", worker)
        self.assertIn("glossaryModelUrl: GLOSSARY_MODEL_PATH", worker)
        self.assertIn("softTimeoutMs: DOCUMENT_SOFT_TIMEOUT_MS", worker)
        self.assertIn("workerInstanceId: WORKER_INSTANCE_ID", worker)

    def test_checker_validates_all_service_worker_install_assets_before_browser_start(self) -> None:
        source = CHECKER.read_text(encoding="utf-8")
        self.assertIn("STATIC_ASSETS_PATTERN", source)
        self.assertIn("def _read_install_assets(site_root: Path)", source)
        self.assertIn('asset.lstrip("/")', source)

        worker = WORKER.read_text(encoding="utf-8")
        match = re.search(r"const STATIC_ASSETS = (\[[^;]+\]);", worker, re.DOTALL)
        self.assertIsNotNone(match)
        static_assets = json.loads(match.group(1))

        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            (site_root / "service-worker.js").write_text(worker, encoding="utf-8")
            required = check_pwa_capabilities._read_install_assets(site_root)
            expected = {
                site_root / "service-worker.js",
                *(site_root / asset.lstrip("/") for asset in static_assets),
            }
            self.assertEqual(set(required), expected)

            with self.assertRaises(check_pwa_capabilities.PwaCapabilityError) as context:
                check_pwa_capabilities.run_check(site_root, None)
        self.assertIn("built site is missing required PWA assets", str(context.exception))

    def test_mobile_visual_workflow_runs_capability_checker(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Check PWA freshness capability messaging", workflow)
        self.assertIn("python scripts/check_pwa_capabilities.py", workflow)
        self.assertIn("build/mobile-visual/pwa-capabilities.json", workflow)


if __name__ == "__main__":
    unittest.main()

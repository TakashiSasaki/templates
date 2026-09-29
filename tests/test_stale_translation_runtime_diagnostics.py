from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/check_stale_translation_runtime.py"
SPEC = importlib.util.spec_from_file_location(
    "check_stale_translation_runtime", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
RUNTIME_CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME_CHECK)


class StaleTranslationRuntimeDiagnosticTests(unittest.TestCase):
    def test_worker_prelude_traces_lifetime_promises_with_rollout_identity(self) -> None:
        prelude = RUNTIME_CHECK._service_worker_diagnostic_prelude(2).decode(
            "utf-8"
        )

        self.assertIn("const SITE_PWA_DIAGNOSTIC_ROLLOUT = 2;", prelude)
        self.assertIn(
            'new Set(["activate", "fetch", "install", "message"])', prelude
        )
        self.assertIn('method + "_pending"', prelude)
        self.assertIn('"respondWith"', prelude)
        self.assertIn('log("skipWaiting_called"', prelude)
        self.assertIn('log("skipWaiting_fulfilled"', prelude)
        self.assertIn('log("skipWaiting_rejected"', prelude)
        self.assertIn("SITE_PWA_SW_EVENT ", prelude)

    def test_failure_writes_partial_evidence_and_phase_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "translation-status.json"
            logs = io.StringIO()
            with patch.object(
                RUNTIME_CHECK,
                "validate",
                side_effect=RuntimeError("synthetic bundle failure"),
            ):
                with redirect_stdout(logs):
                    with self.assertRaisesRegex(
                        RuntimeError, "synthetic bundle failure"
                    ):
                        RUNTIME_CHECK.run(ROOT, ROOT / "missing-bundle", output)

            evidence = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(evidence["status"], "failed")
            self.assertEqual(evidence["phases"][0]["name"], "bundle.validate")
            self.assertEqual(evidence["phases"][0]["status"], "failed")
            self.assertEqual(evidence["error"]["type"], "RuntimeError")
            self.assertIn("SITE_PWA_DIAGNOSTIC", logs.getvalue())
            self.assertEqual(evidence["trace"]["status"], "pending")

    def _write_route_inputs(self, root, statuses=("stale", "current", "missing")):
        site, bundle = root / "site", root / "bundle"
        site.mkdir()
        bundle.mkdir()
        (site / "publication-bundle.json").write_text(json.dumps({"identity": "selected"}))
        records = [{"canonical_destination": f"composition/{status}.md", "status": status,
                    "language": "ja"} for status in statuses]
        relocations = {r["canonical_destination"]: "use/" + r["canonical_destination"] for r in records}
        (site / "presentation.json").write_text(json.dumps({"relocations": relocations}))
        (bundle / "translation-availability.json").write_text(json.dumps({"records": records}))
        return site, bundle

    def test_routes_follow_site_audience_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            site, bundle = self._write_route_inputs(Path(directory))
            routes = RUNTIME_CHECK._translation_routes(site, bundle, {"identity": "selected"})
            self.assertEqual(routes["stale_route"], "/ja/use/composition/stale/")
            self.assertEqual(routes["current_route"], "/ja/use/composition/current/")
            self.assertEqual(routes["missing_route"], "/ja/use/composition/missing/")
            self.assertEqual(routes["canonical_route"], "/use/composition/stale/")

    def test_mismatched_preview_and_publication_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            site, bundle = self._write_route_inputs(Path(directory))
            with self.assertRaisesRegex(ValueError, "identities differ"):
                RUNTIME_CHECK._translation_routes(site, bundle, {"identity": "other"})

    def test_missing_optional_translation_case_reports_prerequisite(self):
        with tempfile.TemporaryDirectory() as directory:
            site, bundle = self._write_route_inputs(Path(directory), ("current", "missing"))
            with self.assertRaisesRegex(ValueError, "needs a stale Japanese translation case"):
                RUNTIME_CHECK._translation_routes(site, bundle, {"identity": "selected"})


if __name__ == "__main__":
    unittest.main()

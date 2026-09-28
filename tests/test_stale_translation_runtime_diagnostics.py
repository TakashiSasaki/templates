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
        self.assertIn("SITE_PWA_SW_EVENT ", prelude)

    def test_failure_writes_partial_evidence_and_phase_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "translation-status.json"
            logs = io.StringIO()
            with patch.object(
                RUNTIME_CHECK,
                "load_lock",
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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
PROOF_PATH = ROOT / "examples/onboarding/task-ledger/browser_proof.py"
PACKAGE = types.ModuleType("task_ledger")
PACKAGE.__path__ = []
CLI = types.ModuleType("task_ledger.cli")
CLI.make_server = lambda *args, **kwargs: None
SPEC = importlib.util.spec_from_file_location("task_ledger_browser_proof_retry_fixture", PROOF_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"could not load Task Ledger browser proof: {PROOF_PATH}")
browser_proof = importlib.util.module_from_spec(SPEC)
with patch.dict(sys.modules, {"task_ledger": PACKAGE, "task_ledger.cli": CLI}):
    SPEC.loader.exec_module(browser_proof)


class TaskLedgerBrowserBootstrapRetryTests(unittest.TestCase):
    def test_raw_timeout_is_classified_as_transport_failure(self) -> None:
        session = object.__new__(browser_proof.BrowserSession)
        session.port = 12345
        with patch.object(browser_proof, "urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(browser_proof._WebDriverTransportError) as raised:
                session.request("POST", "/session", {"capabilities": {}})
        self.assertIn("POST /session transport failed", str(raised.exception))

    def test_constructor_cleans_service_after_bootstrap_transport_failure(self) -> None:
        service = MagicMock()
        service.poll.return_value = None
        service.wait.return_value = 0
        transport = browser_proof._WebDriverTransportError("timed out")

        with patch.object(browser_proof, "driver_path", return_value="/driver"), patch.object(
            browser_proof, "free_port", return_value=43210
        ), patch.object(browser_proof.subprocess, "Popen", return_value=service), patch.object(
            browser_proof.BrowserSession, "wait_ready", return_value=None
        ), patch.object(
            browser_proof.BrowserSession, "start_session", side_effect=transport
        ):
            with self.assertRaises(browser_proof._WebDriverBootstrapError):
                browser_proof.BrowserSession()

        service.terminate.assert_called_once_with()
        service.wait.assert_called_once_with(timeout=5)

    def test_retry_helper_retries_one_bootstrap_failure_with_fresh_session(self) -> None:
        recovered = MagicMock()
        first = browser_proof._WebDriverBootstrapError("first startup failed")
        with patch.object(
            browser_proof,
            "BrowserSession",
            side_effect=[first, recovered],
        ) as constructor:
            self.assertIs(browser_proof.open_browser_session(), recovered)
        self.assertEqual(constructor.call_count, 2)

    def test_retry_helper_fails_closed_after_second_bootstrap_failure(self) -> None:
        first = browser_proof._WebDriverBootstrapError("first startup failed")
        second = browser_proof._WebDriverBootstrapError("second startup failed")
        with patch.object(
            browser_proof,
            "BrowserSession",
            side_effect=[first, second],
        ) as constructor:
            with self.assertRaises(browser_proof.BrowserProofError) as raised:
                browser_proof.open_browser_session()
        self.assertEqual(constructor.call_count, 2)
        self.assertIn("failed after 2 attempts", str(raised.exception))
        self.assertIs(raised.exception.__cause__, second)

    def test_semantic_constructor_error_is_not_retried(self) -> None:
        semantic = browser_proof.BrowserProofError("session not created")
        with patch.object(
            browser_proof,
            "BrowserSession",
            side_effect=semantic,
        ) as constructor:
            with self.assertRaisesRegex(browser_proof.BrowserProofError, "session not created"):
                browser_proof.open_browser_session()
        constructor.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

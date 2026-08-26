from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "tests/fixtures/webapp_browser/browser_probe.py"
SPEC = importlib.util.spec_from_file_location("browser_probe_test_fixture", PROBE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"could not load browser probe fixture: {PROBE_PATH}")
browser_probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(browser_probe)


class BrowserProbeBootstrapRetryTests(unittest.TestCase):
    def test_raw_timeout_is_classified_as_transport_failure(self) -> None:
        session = object.__new__(browser_probe._WebDriverSession)
        session._port = 12345
        with patch.object(browser_probe, "urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(browser_probe._WebDriverTransportError) as raised:
                session._request("POST", "/session", {"capabilities": {}})
        self.assertIn("POST /session transport failed", str(raised.exception))

    def test_constructor_cleans_service_after_bootstrap_transport_failure(self) -> None:
        service = MagicMock()
        service.poll.return_value = None
        service.wait.return_value = 0
        transport = browser_probe._WebDriverTransportError("timed out")

        with patch.object(browser_probe, "_chromedriver_path", return_value="/driver"), patch.object(
            browser_probe, "_free_port", return_value=43210
        ), patch.object(browser_probe.subprocess, "Popen", return_value=service), patch.object(
            browser_probe._WebDriverSession, "_wait_until_ready", return_value=None
        ), patch.object(
            browser_probe._WebDriverSession, "_request", side_effect=transport
        ):
            with self.assertRaises(browser_probe._WebDriverBootstrapError):
                browser_probe._WebDriverSession()

        service.terminate.assert_called_once_with()
        service.wait.assert_called_once_with(timeout=5)

    def test_retry_helper_retries_one_bootstrap_failure_with_fresh_session(self) -> None:
        recovered = MagicMock()
        first = browser_probe._WebDriverBootstrapError("first startup failed")
        with patch.object(
            browser_probe,
            "_WebDriverSession",
            side_effect=[first, recovered],
        ) as constructor:
            self.assertIs(browser_probe._open_webdriver_session(), recovered)
        self.assertEqual(constructor.call_count, 2)

    def test_retry_helper_fails_closed_after_second_bootstrap_failure(self) -> None:
        first = browser_probe._WebDriverBootstrapError("first startup failed")
        second = browser_probe._WebDriverBootstrapError("second startup failed")
        with patch.object(
            browser_probe,
            "_WebDriverSession",
            side_effect=[first, second],
        ) as constructor:
            with self.assertRaises(browser_probe.BrowserProbeError) as raised:
                browser_probe._open_webdriver_session()
        self.assertEqual(constructor.call_count, 2)
        self.assertIn("failed after 2 attempts", str(raised.exception))
        self.assertIs(raised.exception.__cause__, second)

    def test_semantic_constructor_error_is_not_retried(self) -> None:
        semantic = browser_probe.BrowserProbeError("session not created")
        with patch.object(
            browser_probe,
            "_WebDriverSession",
            side_effect=semantic,
        ) as constructor:
            with self.assertRaisesRegex(
                browser_probe.BrowserProbeError,
                "session not created",
            ):
                browser_probe._open_webdriver_session()
        constructor.assert_called_once_with()

    def test_post_session_semantic_failure_is_not_retried(self) -> None:
        class FailingSession:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def navigate(self, url: str) -> None:
                raise browser_probe.BrowserProbeError("semantic navigation failure")

        contract = {
            "viewports": [{"minWidthPx": 320}],
            "inputCapabilities": [],
            "constraints": {
                "horizontalScrolling": "never",
                "zoomSupported": True,
                "orientationIndependent": True,
            },
        }
        with patch.object(
            browser_probe,
            "_open_webdriver_session",
            return_value=FailingSession(),
        ) as opener:
            with self.assertRaisesRegex(
                browser_probe.BrowserProbeError,
                "semantic navigation failure",
            ):
                browser_probe.run_browser_contract_probe("file:///fixture.html", contract)
        opener.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

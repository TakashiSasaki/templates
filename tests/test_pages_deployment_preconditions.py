from __future__ import annotations

import io
import json
import unittest
from urllib.error import HTTPError

from scripts.revalidate_pages_deployment import (
    GitHubAPI,
    GitHubAPIError,
    read_kill_switch,
)


class _Response:
    status = 200

    def __init__(self, value: dict) -> None:
        self.value = value

    def read(self) -> bytes:
        return json.dumps(self.value).encode("utf-8")

    def close(self) -> None:
        pass

    def getcode(self) -> int:
        return self.status


def _api(responses: list[dict | Exception]) -> GitHubAPI:
    pending = iter(responses)

    def opener(_request, timeout=10):
        del timeout
        response = next(pending)
        if isinstance(response, Exception):
            raise response
        return _Response(response)

    return GitHubAPI("TakashiSasaki/templates", "test-token", opener=opener)


def _http_error(status: int) -> HTTPError:
    return HTTPError("https://api.github.com", status, "test", {}, io.BytesIO())


class PagesDeploymentPreconditionTests(unittest.TestCase):
    def test_true_kill_switch_stops(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "kill switch is enabled"):
            read_kill_switch(_api([{"value": "true"}]))

    def test_false_kill_switch_allows_subsequent_gates(self) -> None:
        self.assertEqual(read_kill_switch(_api([{"value": "false"}])), "false")

    def test_missing_kill_switch_uses_default_only_after_authenticated_repo_read(self) -> None:
        api = _api([_http_error(404), {"full_name": "TakashiSasaki/templates"}])
        self.assertEqual(read_kill_switch(api), "false")

    def test_missing_variable_without_repository_confirmation_stops(self) -> None:
        api = _api([_http_error(404), _http_error(403)])
        with self.assertRaises(GitHubAPIError) as context:
            read_kill_switch(api)
        self.assertEqual(context.exception.status, 403)

    def test_manual_context_confirms_false_when_token_cannot_read_variables(self) -> None:
        api = _api([_http_error(403)])
        self.assertEqual(
            read_kill_switch(api, expected_manual_value="false"),
            "false",
        )

    def test_manual_context_true_still_stops_when_token_cannot_read_variables(self) -> None:
        api = _api([_http_error(403)])
        with self.assertRaisesRegex(RuntimeError, "kill switch is enabled"):
            read_kill_switch(api, expected_manual_value="true")

    def test_malformed_manual_context_stops_before_variable_read(self) -> None:
        api = _api([])
        with self.assertRaisesRegex(RuntimeError, "manual kill-switch context is invalid"):
            read_kill_switch(api, expected_manual_value="maybe")

    def test_automatic_lane_never_uses_manual_context_fallback(self) -> None:
        api = _api([_http_error(403)])
        with self.assertRaises(GitHubAPIError) as context:
            read_kill_switch(api, expected_manual_value="false", automatic=True)
        self.assertEqual(context.exception.status, 403)

    def test_authentication_failure_stops(self) -> None:
        with self.assertRaises(GitHubAPIError) as context:
            read_kill_switch(_api([_http_error(401)]))
        self.assertEqual(context.exception.status, 401)

    def test_server_failure_stops(self) -> None:
        with self.assertRaises(GitHubAPIError) as context:
            read_kill_switch(_api([_http_error(500)]))
        self.assertEqual(context.exception.status, 500)

    def test_rate_limit_failure_stops(self) -> None:
        with self.assertRaises(GitHubAPIError) as context:
            read_kill_switch(_api([_http_error(429)]))
        self.assertEqual(context.exception.status, 429)

    def test_non_kill_switch_missing_variable_never_gets_a_default(self) -> None:
        api = _api([_http_error(404)])
        with self.assertRaises(GitHubAPIError) as context:
            api.repository_variable("PUBLICATION_AUTOMATION_MODE")
        self.assertEqual(context.exception.status, 404)


if __name__ == "__main__":
    unittest.main()

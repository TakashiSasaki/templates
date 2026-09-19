#!/usr/bin/env python3
"""Revalidate the exact inputs immediately before a Pages deployment.

This file is checked out from the workflow's own immutable revision.  It is
deliberately stdlib-only and does not execute provider, artifact, or candidate
checkout code.  GitHub API failures are deployment failures: the verifier
never guesses that a mutable authorization value is safe.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
ARTIFACT_ID = re.compile(r"^[1-9][0-9]*$")
GITHUB_API = "https://api.github.com"
KILL_SWITCH = "PUBLICATION_AUTOMATION_KILL_SWITCH"


class DeploymentCheckError(RuntimeError):
    """A deployment precondition could not be established or was rejected."""


class GitHubAPIError(DeploymentCheckError):
    """A GitHub API request did not produce the required successful response."""

    def __init__(self, path: str, message: str, *, status: int | None = None) -> None:
        self.path = path
        self.status = status
        suffix = f" (HTTP {status})" if status is not None else ""
        super().__init__(f"GitHub API request {path} failed{suffix}: {message}")


class GitHubAPI:
    """Small status-aware read-only GitHub REST client.

    ``opener`` is injectable so the status/error behavior can be tested
    without contacting GitHub.  The production caller uses ``urlopen`` with
    the workflow token and a fixed api.github.com origin.
    """

    def __init__(
        self,
        repository: str,
        token: str,
        *,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not re.fullmatch(r"[^/]+/[^/]+", repository):
            raise DeploymentCheckError("GITHUB_REPOSITORY must be owner/name")
        if not token:
            raise DeploymentCheckError("GH_TOKEN is required for deployment revalidation")
        self.repository = repository
        self.token = token
        self.opener = opener

    def get_json(self, path: str) -> dict[str, Any]:
        if path.startswith("/") or "?" in path or "#" in path:
            raise DeploymentCheckError("deployment API path is not a fixed read-only route")
        request = Request(
            f"{GITHUB_API}/{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )
        response: Any = None
        try:
            response = self.opener(request, timeout=10)
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            body = response.read()
        except HTTPError as exc:
            # Reading the response body is intentionally unnecessary.  It may
            # contain user-controlled text and never changes the fail-closed
            # decision; the explicit HTTP status is the useful evidence.
            raise GitHubAPIError(path, "the API did not return a successful response", status=exc.code) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise GitHubAPIError(path, type(exc).__name__) from exc
        finally:
            if response is not None and hasattr(response, "close"):
                response.close()

        if status != 200:
            raise GitHubAPIError(path, "the API did not return HTTP 200", status=status)
        try:
            value = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        except (UnicodeError, TypeError, ValueError) as exc:
            raise GitHubAPIError(path, "the successful response was not valid JSON", status=status) from exc
        if not isinstance(value, dict):
            raise GitHubAPIError(path, "the successful response was not a JSON object", status=status)
        return value

    def repository_variable(self, name: str, *, allow_confirmed_missing: bool = False) -> str:
        path = f"repos/{self.repository}/actions/variables/{name}"
        try:
            value = self.get_json(path)
        except GitHubAPIError as exc:
            if not (allow_confirmed_missing and exc.status == 404):
                raise
            # A variable GET returning 404 is only treated as the documented
            # absent-variable case after an authenticated repository read also
            # succeeds.  Authentication, permission, rate-limit, transport,
            # and server failures never become a default value.
            metadata = self.get_json(f"repos/{self.repository}")
            if metadata.get("full_name") != self.repository:
                raise DeploymentCheckError("repository metadata did not identify the expected repository")
            return "false"
        result = value.get("value")
        if not isinstance(result, str):
            raise DeploymentCheckError(f"publication variable {name} has no string value")
        return result


def read_kill_switch(
    api: GitHubAPI,
    *,
    expected_manual_value: str | None = None,
    automatic: bool = False,
) -> str:
    """Read the kill switch, using the manual workflow context when needed.

    ``GITHUB_TOKEN`` can evaluate ``vars`` in workflow expressions but may not
    have permission to read the repository-variable REST endpoint. The manual
    lane therefore supplies the exact value already used by its job
    conditions. A REST 403 may use that value only for the manual lane; the
    automatic lane remains API-only and fail-closed.
    """

    try:
        value = api.repository_variable(KILL_SWITCH, allow_confirmed_missing=True)
    except GitHubAPIError as exc:
        if automatic or exc.status != 403 or expected_manual_value not in {"false", "true"}:
            raise
        value = expected_manual_value
    if value != "false":
        raise DeploymentCheckError("publication kill switch is enabled before Pages deployment")
    return value


def _json_environment(name: str) -> Any:
    try:
        return json.loads(os.environ[name])
    except (KeyError, UnicodeError, ValueError, TypeError) as exc:
        raise DeploymentCheckError(f"{name} is not valid JSON") from exc


def revalidate(api: GitHubAPI, environment: dict[str, str] | None = None) -> dict[str, Any]:
    """Run all final deployment checks and return the immutable selection."""

    values = dict(os.environ if environment is None else environment)
    repository = values.get("GITHUB_REPOSITORY", "")
    if repository != api.repository:
        raise DeploymentCheckError("deployment repository does not match the API client repository")

    automatic = values.get("AUTOMATIC", "").lower() == "true"
    read_kill_switch(
        api,
        expected_manual_value=values.get("EXPECTED_KILL_SWITCH"),
        automatic=automatic,
    )

    receipt = _json_environment("BUILD_RECEIPT")
    required_receipt = {
        "repository", "producer", "identity", "run_id", "attempt",
        "workflow_head", "artifact_id", "archive_digest", "artifact_name",
    }
    if not isinstance(receipt, dict) or not required_receipt <= set(receipt):
        raise DeploymentCheckError("the qualified build did not carry a complete Integration receipt")

    trusted = receipt.get("trusted_receipt")
    if automatic:
        if not isinstance(trusted, dict):
            raise DeploymentCheckError("the automatic build did not carry a trusted Integration receipt")
        for field in ("policy_revision", "controller_revision"):
            if not FULL_SHA.fullmatch(str(trusted.get(field, ""))):
                raise DeploymentCheckError(f"trusted receipt {field} is not an exact SHA")
        current = {
            "mode": api.repository_variable("PUBLICATION_AUTOMATION_MODE"),
            "authorized": api.repository_variable("PUBLICATION_AUTOMATION_AUTHORIZED"),
            "policy": api.repository_variable("PUBLICATION_POLICY_REVISION"),
            "controller": api.repository_variable("PUBLICATION_CONTROLLER_REVISION"),
        }
        if current["mode"] != "auto-publish" or current["authorized"] != "true":
            raise DeploymentCheckError("publication authorization changed before Pages deployment")
        if current["policy"] != values.get("EXPECTED_POLICY_REVISION"):
            raise DeploymentCheckError("trusted Policy revision changed before Pages deployment")
        if current["controller"] != values.get("EXPECTED_CONTROLLER_REVISION"):
            raise DeploymentCheckError("trusted controller revision changed before Pages deployment")
        if trusted["policy_revision"] != current["policy"] or trusted["controller_revision"] != current["controller"]:
            raise DeploymentCheckError("trusted receipt identities differ from active automation pins")

    expected_site = values.get("EXPECTED_SITE_REVISION", "")
    ref = api.get_json(f"repos/{repository}/git/ref/heads/site")
    if ref.get("object", {}).get("sha") != expected_site:
        raise DeploymentCheckError("Site branch advanced before Pages deployment")

    artifact_id = values.get("EXPECTED_ARTIFACT_ID", "")
    if not ARTIFACT_ID.fullmatch(artifact_id):
        raise DeploymentCheckError("Pages artifact id is invalid before deployment")
    artifact = api.get_json(f"repos/{repository}/actions/artifacts/{artifact_id}")
    if artifact.get("id") != int(artifact_id) or artifact.get("name") != "github-pages":
        raise DeploymentCheckError("Pages artifact identity changed before deployment")
    if artifact.get("expired") is not False:
        raise DeploymentCheckError("Pages artifact is missing or expired before deployment")
    if artifact.get("digest") != values.get("EXPECTED_ARTIFACT_DIGEST"):
        raise DeploymentCheckError("Pages artifact digest changed before deployment")
    try:
        expected_run_id = int(values["GITHUB_RUN_ID"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DeploymentCheckError("GITHUB_RUN_ID is invalid") from exc
    if artifact.get("workflow_run", {}).get("id") != expected_run_id:
        raise DeploymentCheckError("Pages artifact belongs to a different deployment run")

    inputs = _json_environment("EXPECTED_BUILD_INPUTS")
    if not isinstance(inputs, dict):
        raise DeploymentCheckError("Pages build inputs are not an object")
    if inputs.get("site") != expected_site:
        raise DeploymentCheckError("Pages artifact was built from a different Site revision")
    bundle = inputs.get("publication_bundle")
    producer = bundle.get("producer") if isinstance(bundle, dict) else None
    if not isinstance(bundle, dict) or not isinstance(bundle.get("identity"), str) or not bundle["identity"]:
        raise DeploymentCheckError("Pages artifact is missing the selected Bundle identity")
    if not isinstance(producer, dict):
        raise DeploymentCheckError("Pages artifact is missing the selected Bundle producer")
    if (
        receipt.get("producer") != producer.get("revision")
        or receipt.get("identity") != bundle.get("identity")
        or (automatic and trusted.get("bundle_content_digest") != bundle.get("content_digest"))
    ):
        raise DeploymentCheckError("trusted receipt and final artifact selected different Bundle inputs")

    return {
        "artifact_id": artifact["id"],
        "digest": artifact["digest"],
        "site_revision": inputs["site"],
        "bundle_identity": bundle["identity"],
    }


def main() -> int:
    try:
        repository = os.environ["GITHUB_REPOSITORY"]
        token = os.environ.get("GH_TOKEN", "")
        result = revalidate(GitHubAPI(repository, token))
    except (DeploymentCheckError, KeyError) as exc:
        print(f"Pages deployment precondition failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

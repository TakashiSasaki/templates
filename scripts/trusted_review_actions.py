"""GitHub Actions authenticated observation for trusted-review bootstrap.

The document produced here is data, not authority by itself. Production callers
must verify its GitHub Artifact Attestation and compare it with a fresh API
observation before accepting it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

GITHUB_API = "https://api.github.com"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
GH_EXECUTABLE = "/usr/bin/gh"
REPOSITORY = "TakashiSasaki/templates"
REPOSITORY_ID = "1315875002"
OWNER_ID = "556958"
POLICY_BASE_REF = "policy"
DEFAULT_REF = "refs/heads/site"
WORKFLOW_PATH = ".github/workflows/trusted-review-bootstrap.yml"
WORKFLOW_REF = f"{REPOSITORY}/{WORKFLOW_PATH}@{DEFAULT_REF}"
SIGNER_WORKFLOW = f"{REPOSITORY}/{WORKFLOW_PATH}"
CERT_IDENTITY = f"https://github.com/{REPOSITORY}/{WORKFLOW_PATH}@{DEFAULT_REF}"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
DECIMAL_ID = re.compile(r"^[1-9][0-9]*$")


class TrustedObservationError(ValueError):
    """Raised when provider identity or its producer provenance is incomplete."""


@dataclass(frozen=True)
class ActionsRunIdentity:
    repository: str
    repository_id: str
    run_id: str
    run_attempt: int
    event: str
    ref: str
    workflow_ref: str
    workflow_sha: str
    source_sha: str
    actor: str
    actor_id: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> ActionsRunIdentity:
        values = os.environ if env is None else env
        repository = values.get("GITHUB_REPOSITORY", "")
        repository_id = values.get("GITHUB_REPOSITORY_ID", "")
        run_id = values.get("GITHUB_RUN_ID", "")
        run_attempt_raw = values.get("GITHUB_RUN_ATTEMPT", "")
        event = values.get("GITHUB_EVENT_NAME", "")
        ref = values.get("GITHUB_REF", "")
        workflow_ref = values.get("GITHUB_WORKFLOW_REF", "")
        workflow_sha = values.get("GITHUB_WORKFLOW_SHA", "")
        source_sha = values.get("GITHUB_SHA", "")
        actor = values.get("TRUSTED_REVIEW_ACTOR_LOGIN", "")
        actor_id = values.get("TRUSTED_REVIEW_ACTOR_ID", "")

        if repository != REPOSITORY:
            raise TrustedObservationError("workflow repository identity is not trusted")
        if repository_id != REPOSITORY_ID:
            raise TrustedObservationError(
                "GITHUB_REPOSITORY_ID does not match the trusted repository"
            )
        if not DECIMAL_ID.fullmatch(run_id):
            raise TrustedObservationError("GITHUB_RUN_ID is missing or invalid")
        if run_attempt_raw != "1":
            raise TrustedObservationError(
                "trusted review requires the original workflow attempt; dispatch a fresh run"
            )
        if event != "workflow_dispatch" or ref != DEFAULT_REF:
            raise TrustedObservationError(
                "trusted review accepts only default-branch workflow_dispatch"
            )
        if workflow_ref != WORKFLOW_REF:
            raise TrustedObservationError("trusted workflow path or ref has drifted")
        if not SHA1.fullmatch(workflow_sha):
            raise TrustedObservationError("trusted workflow SHA is missing or invalid")
        if not SHA1.fullmatch(source_sha):
            raise TrustedObservationError("workflow source SHA is missing or invalid")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", actor):
            raise TrustedObservationError("trusted workflow actor login is missing or invalid")
        if not DECIMAL_ID.fullmatch(actor_id):
            raise TrustedObservationError("trusted workflow actor ID is missing or invalid")

        return cls(
            repository=repository,
            repository_id=repository_id,
            run_id=run_id,
            run_attempt=int(run_attempt_raw),
            event=event,
            ref=ref,
            workflow_ref=workflow_ref,
            workflow_sha=workflow_sha,
            source_sha=source_sha,
            actor=actor,
            actor_id=actor_id,
        )


class GitHubApi:
    """Read-only GitHub API client which never logs or serializes its token."""

    def __init__(
        self,
        token: str,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
        api_origin: str = GITHUB_API,
    ) -> None:
        if not token or "\n" in token or "\r" in token:
            raise TrustedObservationError("GITHUB_TOKEN is required")
        if api_origin != GITHUB_API:
            raise TrustedObservationError("GitHub API origin is not trusted")
        self._token = token
        self._opener = opener

    def get(self, path: str) -> dict[str, Any]:
        if not path.startswith("/") or ".." in path or "?" in path or "#" in path:
            raise TrustedObservationError("invalid GitHub API path")
        request = urllib.request.Request(
            GITHUB_API + path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2026-03-10",
            },
        )
        try:
            with self._opener(request, timeout=20) as response:
                payload = response.read()
        except (OSError, urllib.error.URLError) as exc:
            raise TrustedObservationError("authenticated GitHub API request failed") from exc
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TrustedObservationError("GitHub API returned malformed JSON") from exc
        if not isinstance(value, dict):
            raise TrustedObservationError("GitHub API response must be an object")
        return value

    def observe(self, number: int, run: ActionsRunIdentity) -> dict[str, Any]:
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise TrustedObservationError("pull request number must be a positive integer")
        owner, repo = run.repository.split("/", 1)
        encoded_repo = f"{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(repo, safe='')}"
        repository = self.get(f"/repos/{encoded_repo}")
        if str(repository.get("id")) != run.repository_id:
            raise TrustedObservationError(
                "GitHub API repository ID does not match workflow context"
            )
        full_name = repository.get("full_name")
        owner_data = repository.get("owner")
        if full_name != run.repository or not isinstance(owner_data, dict):
            raise TrustedObservationError("GitHub API repository name/owner is inconsistent")
        owner_id = owner_data.get("id")
        if not isinstance(owner_id, int) or str(owner_id) != OWNER_ID:
            raise TrustedObservationError(
                "GitHub API owner ID does not match the trusted repository"
            )

        pull = self.get(f"/repos/{encoded_repo}/pulls/{number}")
        if pull.get("number") != number or not pull.get("id") or not pull.get("node_id"):
            raise TrustedObservationError("GitHub API pull-request identity is incomplete")
        author = pull.get("user")
        if (
            not isinstance(author, dict)
            or not isinstance(author.get("id"), int)
            or not isinstance(author.get("login"), str)
        ):
            raise TrustedObservationError("GitHub API pull-request author identity is incomplete")
        if str(author["id"]) == run.actor_id or author["login"].casefold() == run.actor.casefold():
            raise TrustedObservationError(
                "pull-request author cannot dispatch an independent review "
                "of their own pull request"
            )
        if pull.get("state") != "open":
            raise TrustedObservationError("pull request is not open")
        base = pull.get("base")
        head = pull.get("head")
        if not isinstance(base, dict) or not isinstance(head, dict):
            raise TrustedObservationError("GitHub API pull-request refs are incomplete")
        base_repo = base.get("repo")
        if not isinstance(base_repo, dict) or str(base_repo.get("id")) != run.repository_id:
            raise TrustedObservationError("pull request base repository identity does not match")
        base_ref = base.get("ref")
        if base_ref != POLICY_BASE_REF:
            raise TrustedObservationError(
                "pull request base ref is not the trusted Policy branch"
            )

        base_sha = _full_sha(base.get("sha"), "pull request base SHA")
        head_sha = _full_sha(head.get("sha"), "pull request head SHA")
        base_commit = self.get(f"/repos/{encoded_repo}/git/commits/{base_sha}")
        head_repo = head.get("repo")
        if not isinstance(head_repo, dict) or not isinstance(head_repo.get("full_name"), str):
            raise TrustedObservationError("pull request head repository is unavailable")
        head_owner, separator, head_name = head_repo["full_name"].partition("/")
        if (
            not separator
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", head_owner)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", head_name)
        ):
            raise TrustedObservationError("pull request head repository name is invalid")
        head_slug = (
            f"{urllib.parse.quote(head_owner, safe='')}/{urllib.parse.quote(head_name, safe='')}"
        )
        head_commit = self.get(f"/repos/{head_slug}/git/commits/{head_sha}")
        base_tree = _commit_tree(base_commit, "pull request base tree SHA")
        head_tree = _commit_tree(head_commit, "pull request head tree SHA")
        if base_commit.get("sha") != base_sha or head_commit.get("sha") != head_sha:
            raise TrustedObservationError("GitHub API commit identity did not match requested SHA")

        return {
            "schema_version": 1,
            "provider": "github",
            "repository": {"id": str(repository["id"]), "name_with_owner": full_name},
            "pull_request": {
                "id": str(pull["id"]),
                "node_id": pull["node_id"],
                "number": number,
                "author_id": str(author["id"]),
                "author_login": author["login"],
                "base": {"ref": base_ref, "sha": base_sha, "tree": base_tree},
                "head": {"sha": head_sha, "tree": head_tree},
            },
            "observation": {
                "retrieved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "api_origin": GITHUB_API,
                "run_id": run.run_id,
                "run_attempt": run.run_attempt,
                "event": run.event,
            },
            "producer": {
                "issuer": OIDC_ISSUER,
                "repository_id": run.repository_id,
                "owner_id": str(owner_id),
                "workflow_ref": run.workflow_ref,
                "workflow_sha": run.workflow_sha,
                "source_sha": run.source_sha,
                "actor_id": run.actor_id,
                "actor_login": run.actor,
            },
        }


def _full_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA1.fullmatch(value):
        raise TrustedObservationError(f"{label} is missing or invalid")
    return value


def _commit_tree(commit: dict[str, Any], label: str) -> str:
    tree = commit.get("tree")
    if not isinstance(tree, dict):
        tree = (commit.get("commit") or {}).get("tree")
    return _full_sha((tree or {}).get("sha"), label)


def canonical_observation_bytes(document: dict[str, Any]) -> bytes:
    validate_observation(document)
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TrustedObservationError("duplicate JSON key in provider observation")
        result[key] = value
    return result


@lru_cache(maxsize=1)
def _observation_schema() -> dict[str, Any]:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "schemas/trusted-review-provider-observation.schema.json"
    )
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise TrustedObservationError(
            "trusted provider-observation schema is unavailable or invalid"
        ) from exc
    return schema


def validate_observation(document: Any) -> None:
    try:
        Draft202012Validator(_observation_schema(), format_checker=FormatChecker()).validate(
            document
        )
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        raise TrustedObservationError(
            f"provider observation violates its schema at {path}"
        ) from exc


def provider_identity(document: dict[str, Any], raw_bytes: bytes) -> dict[str, Any]:
    """Map verified observation bytes to the existing handoff target shape.

    The returned authenticated marker is only a claim until the production
    adapter supplied to validate_provider_identity verifies the attestation.
    """
    validate_observation(document)
    repo = document["repository"]
    pull = document["pull_request"]
    run = document["observation"]
    producer = document["producer"]
    return {
        "name": "github",
        "repository": {"id": repo["id"], "name_with_owner": repo["name_with_owner"]},
        "pull_request": {
            "id": pull["id"],
            "node_id": pull["node_id"],
            "number": pull["number"],
            "base_ref_name": pull["base"]["ref"],
            "base_ref_oid": pull["base"]["sha"],
            "base_tree": pull["base"]["tree"],
            "head_ref_oid": pull["head"]["sha"],
            "head_tree": pull["head"]["tree"],
        },
        "observation_evidence": {
            "source": "github_artifact_attestation",
            "authenticated": True,
            "evidence_status": "authenticated",
            "retrieved_at": run["retrieved_at"],
            "verifier": None,
        },
        "provider_observation": {
            "adapter": {
                "tool": "GitHub Artifact Attestations",
                "workflow_ref": producer["workflow_ref"],
            },
            "observation_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "run_id": run["run_id"],
            "run_attempt": run["run_attempt"],
            "workflow_sha": producer["workflow_sha"],
            "source_sha": producer["source_sha"],
            "retrieved_at": run["retrieved_at"],
        },
    }


class GitHubActionsObservationVerifier:
    """Verifies observation bytes, signer identity, run identity and live API state."""

    name = "github-actions-artifact-attestation-v1"

    def __init__(
        self,
        observation_path: Path,
        *,
        token: str | None = None,
        run_identity: ActionsRunIdentity | None = None,
        api: GitHubApi | None = None,
        gh_executable: str = GH_EXECUTABLE,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self.observation_path = observation_path.expanduser().resolve()
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN", "")
        if not self.token:
            raise TrustedObservationError("GITHUB_TOKEN is required for production verification")
        self.run_identity = run_identity or ActionsRunIdentity.from_env()
        self.api = api or GitHubApi(self.token)
        self.gh_executable = gh_executable
        self.runner = runner
        self.production_capable = (
            token is None
            and run_identity is None
            and api is None
            and gh_executable == GH_EXECUTABLE
            and runner is subprocess.run
        )

    def verify(
        self,
        identity: dict[str, Any],
        provider_observation: dict[str, Any] | None = None,
    ) -> str:
        """Verify either a provider identity or a separate target/observation pair."""
        if provider_observation is None:
            provider_observation = identity.get("provider_observation")
            if not isinstance(provider_observation, dict):
                raise TrustedObservationError("provider identity is missing observation binding")
        elif not isinstance(provider_observation, dict):
            raise TrustedObservationError("provider observation binding must be an object")
        return self.verify_target(identity, provider_observation)

    def verify_target(self, target: dict[str, Any], provider_observation: dict[str, Any]) -> str:
        try:
            raw = self.observation_path.read_bytes()
            document = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TrustedObservationError(
                "provider observation file is unavailable or malformed"
            ) from exc
        validate_observation(document)
        digest = hashlib.sha256(raw).hexdigest()
        if provider_observation.get("observation_sha256") != digest:
            raise TrustedObservationError("provider observation digest does not match handoff")
        run = self.run_identity
        observed_run = document["observation"]
        producer = document["producer"]
        if (
            observed_run.get("run_id") != run.run_id
            or observed_run.get("run_attempt") != run.run_attempt
        ):
            raise TrustedObservationError(
                "provider observation was replayed from another workflow run"
            )
        if observed_run.get("event") != run.event:
            raise TrustedObservationError("provider observation event does not match current run")
        if (
            producer.get("workflow_ref") != run.workflow_ref
            or producer.get("workflow_sha") != run.workflow_sha
        ):
            raise TrustedObservationError(
                "provider observation workflow identity is stale or mismatched"
            )
        if producer.get("repository_id") != run.repository_id:
            raise TrustedObservationError(
                "provider observation repository ID does not match current run"
            )
        if producer.get("actor_id") != run.actor_id or producer.get("actor_login") != run.actor:
            raise TrustedObservationError(
                "provider observation dispatch actor does not match current workflow actor"
            )

        api_document = self.api.observe(document["pull_request"]["number"], run)
        if _observation_identity(api_document) != _observation_identity(document):
            raise TrustedObservationError(
                "provider observation is stale or differs from live GitHub API"
            )
        self._verify_attestation(digest, document)
        _compare_target(target, document)
        return self.name

    def _verify_attestation(self, observation_sha256: str, document: dict[str, Any]) -> None:
        run = self.run_identity
        command = [
            self.gh_executable,
            "attestation",
            "verify",
            str(self.observation_path),
            "--repo",
            REPOSITORY,
            "--signer-workflow",
            SIGNER_WORKFLOW,
            "--signer-digest",
            run.workflow_sha,
            "--source-ref",
            DEFAULT_REF,
            "--source-digest",
            run.source_sha,
            "--cert-identity",
            CERT_IDENTITY,
            "--cert-oidc-issuer",
            OIDC_ISSUER,
            "--deny-self-hosted-runners",
            "--format",
            "json",
        ]
        try:
            result = self.runner(command, check=True, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as exc:
            raise TrustedObservationError(
                "GitHub Artifact Attestation verification failed"
            ) from exc
        try:
            verified = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            raise TrustedObservationError("attestation verifier returned malformed JSON") from exc
        if not isinstance(verified, list) or len(verified) != 1:
            raise TrustedObservationError("attestation verifier did not return exactly one result")
        item = verified[0]
        verification = item.get("verificationResult") if isinstance(item, dict) else None
        if not isinstance(verification, dict):
            raise TrustedObservationError("attestation verification result is incomplete")
        signature = verification.get("signature") or {}
        certificate = signature.get("certificate") or {}
        statement = verification.get("statement") or {}
        owner_id = str(document["producer"]["owner_id"])
        _verify_attestation_claims(certificate, statement, run, observation_sha256, owner_id)


def _observation_identity(document: dict[str, Any]) -> tuple[Any, ...]:
    repository = document["repository"]
    pull = document["pull_request"]
    return (
        repository["id"],
        repository["name_with_owner"],
        pull["id"],
        pull["node_id"],
        pull["number"],
        pull["base"]["ref"],
        pull["base"]["sha"],
        pull["base"]["tree"],
        pull["head"]["sha"],
        pull["head"]["tree"],
        document["observation"]["run_id"],
        document["observation"]["run_attempt"],
        document["producer"]["owner_id"],
        document["producer"]["workflow_ref"],
        document["producer"]["workflow_sha"],
        document["producer"]["source_sha"],
        document["producer"]["actor_id"],
        document["producer"]["actor_login"],
        pull["author_id"],
        pull["author_login"],
    )


def _compare_target(target: dict[str, Any], document: dict[str, Any]) -> None:
    repository = target.get("repository") or {}
    pull = target.get("pull_request") or {}
    repo = document["repository"]
    observed_pull = document["pull_request"]
    checks = {
        "repository id": (repository.get("id"), repo["id"]),
        "repository name": (repository.get("name_with_owner"), repo["name_with_owner"]),
        "pull request id": (pull.get("id"), observed_pull["id"]),
        "pull request number": (pull.get("number"), observed_pull["number"]),
        "base ref": (pull.get("base_ref_name"), observed_pull["base"]["ref"]),
        "base commit": (pull.get("base_ref_oid"), observed_pull["base"]["sha"]),
        "base tree": (pull.get("base_tree"), observed_pull["base"]["tree"]),
        "head commit": (pull.get("head_ref_oid"), observed_pull["head"]["sha"]),
        "head tree": (pull.get("head_tree"), observed_pull["head"]["tree"]),
        "pull request node ID": (pull.get("node_id"), observed_pull["node_id"]),
    }
    for label, (actual, expected) in checks.items():
        if actual != expected:
            raise TrustedObservationError(
                f"provider observation {label} does not match handoff target"
            )


def _verify_attestation_claims(
    certificate: dict[str, Any],
    statement: dict[str, Any],
    run: ActionsRunIdentity,
    subject_sha256: str,
    owner_id: str,
) -> None:
    if not isinstance(certificate, dict) or not isinstance(statement, dict):
        raise TrustedObservationError("verified attestation is missing certificate or statement")
    san = certificate.get("subjectAlternativeName")
    if not isinstance(san, dict) or san.get("type") != "URI" or san.get("value") != CERT_IDENTITY:
        raise TrustedObservationError("attestation certificate workflow identity is mismatched")
    expected_identity = {
        "issuer": OIDC_ISSUER,
        "githubWorkflowRepository": REPOSITORY,
        "githubWorkflowRef": DEFAULT_REF,
        "githubWorkflowSHA": run.workflow_sha,
        "buildSignerURI": CERT_IDENTITY,
        "buildSignerDigest": run.workflow_sha,
        "buildConfigURI": CERT_IDENTITY,
        "buildConfigDigest": run.workflow_sha,
        "buildTrigger": "workflow_dispatch",
        "githubWorkflowTrigger": "workflow_dispatch",
        "sourceRepositoryURI": f"https://github.com/{REPOSITORY}",
        "sourceRepositoryDigest": run.source_sha,
        "sourceRepositoryRef": DEFAULT_REF,
        "sourceRepositoryIdentifier": run.repository_id,
        "sourceRepositoryOwnerIdentifier": owner_id,
        "runnerEnvironment": "github-hosted",
    }
    for name, expected in expected_identity.items():
        if certificate.get(name) != expected:
            raise TrustedObservationError(
                f"attestation certificate claim {name} is missing or mismatched"
            )
    run_uri = (
        f"https://github.com/{REPOSITORY}/actions/runs/{run.run_id}/attempts/{run.run_attempt}"
    )
    if certificate.get("runInvocationURI") != run_uri:
        raise TrustedObservationError("attestation belongs to a different workflow run or attempt")

    subjects = statement.get("subject")
    if not isinstance(subjects, list) or len(subjects) != 1:
        raise TrustedObservationError("attestation must bind exactly one observation subject")
    digest = subjects[0].get("digest") if isinstance(subjects[0], dict) else None
    if not isinstance(digest, dict) or digest.get("sha256") != subject_sha256 or len(digest) != 1:
        raise TrustedObservationError("attestation subject digest does not match observation bytes")


def write_observation(number: int, output: Path, *, env: dict[str, str] | None = None) -> None:
    values = os.environ if env is None else env
    run = ActionsRunIdentity.from_env(dict(values))
    token = values.get("GITHUB_TOKEN", "")
    api = GitHubApi(token)
    document = api.observe(number, run)
    destination = output.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise TrustedObservationError("provider observation output already exists")
    for parent in reversed(destination.parents):
        if parent.is_symlink():
            raise TrustedObservationError("provider observation output traverses a symbolic link")
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(destination, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_observation_bytes(document))
    except FileExistsError as exc:
        raise TrustedObservationError("provider observation output already exists") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Produce a trusted GitHub PR observation for Actions attestation."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    observe = sub.add_parser("observe", help="Read pull-request identity through GitHub API.")
    observe.add_argument("--pr-number", type=int, required=True)
    observe.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        write_observation(args.pr_number, args.output)
        print("GITHUB_PROVIDER_OBSERVATION_READY")
        return 0
    except (TrustedObservationError, OSError) as exc:
        print(f"trusted GitHub observation error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

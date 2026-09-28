from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import prepare_trusted_review_handoff as handoff
from scripts import trusted_review_actions as actions

REPO_ID = "1315875002"
OWNER_ID = "556958"
WORKFLOW_SHA = "a" * 40
BASE_SHA = "b" * 40
BASE_TREE = "c" * 40
HEAD_SHA = "d" * 40
HEAD_TREE = "e" * 40


def run_identity() -> actions.ActionsRunIdentity:
    return actions.ActionsRunIdentity(
        repository=actions.REPOSITORY,
        repository_id=REPO_ID,
        run_id="73124",
        run_attempt=1,
        event="workflow_dispatch",
        ref=actions.DEFAULT_REF,
        workflow_ref=actions.WORKFLOW_REF,
        workflow_sha=WORKFLOW_SHA,
        source_sha="f" * 40,
        actor="maintainer",
        actor_id="9001",
        job="bootstrap",
    )


def observation(run: actions.ActionsRunIdentity | None = None) -> dict[str, Any]:
    identity = run or run_identity()
    return {
        "schema_version": 1,
        "provider": "github",
        "repository": {"id": REPO_ID, "name_with_owner": actions.REPOSITORY},
        "pull_request": {
            "id": "81001",
            "node_id": "PR_kwDOExample",
            "number": 97,
            "author_id": "9002",
            "author_login": "contributor",
            "base": {"ref": "policy", "sha": BASE_SHA, "tree": BASE_TREE},
            "head": {"sha": HEAD_SHA, "tree": HEAD_TREE},
        },
        "observation": {
            "retrieved_at": "2026-09-28T00:00:00Z",
            "api_origin": actions.GITHUB_API,
            "run_id": identity.run_id,
            "run_attempt": identity.run_attempt,
            "event": identity.event,
        },
        "producer": {
            "issuer": actions.OIDC_ISSUER,
            "repository_id": identity.repository_id,
            "owner_id": OWNER_ID,
            "workflow_ref": identity.workflow_ref,
            "workflow_sha": identity.workflow_sha,
            "source_sha": identity.source_sha,
            "actor_id": identity.actor_id,
            "actor_login": identity.actor,
            "job": identity.job,
        },
    }


class StaticApi:
    def __init__(self, current: dict[str, Any] | None = None) -> None:
        self.current = current or observation()
        self.seen_number: int | None = None

    def observe(self, number: int, run: actions.ActionsRunIdentity) -> dict[str, Any]:
        self.seen_number = number
        result = copy.deepcopy(self.current)
        result["observation"]["retrieved_at"] = "2026-09-28T00:00:01Z"
        return result


class ResultRunner:
    def __init__(self, output_factory) -> None:
        self.output_factory = output_factory
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> SimpleNamespace:
        self.calls.append(command)
        return SimpleNamespace(stdout=json.dumps(self.output_factory()), stderr="", returncode=0)


def verified_attestation(
    document: dict[str, Any], *, changed: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    doc_bytes = actions.canonical_observation_bytes(document)
    run = run_identity()
    cert = {
        "issuer": actions.OIDC_ISSUER,
        "subjectAlternativeName": {"type": "URI", "value": actions.CERT_IDENTITY},
        "githubWorkflowRepository": actions.REPOSITORY,
        "githubWorkflowRef": actions.DEFAULT_REF,
        "githubWorkflowSHA": WORKFLOW_SHA,
        "buildSignerURI": actions.CERT_IDENTITY,
        "buildSignerDigest": WORKFLOW_SHA,
        "buildConfigURI": actions.CERT_IDENTITY,
        "buildConfigDigest": WORKFLOW_SHA,
        "buildTrigger": "workflow_dispatch",
        "githubWorkflowTrigger": "workflow_dispatch",
        "sourceRepositoryURI": f"https://github.com/{actions.REPOSITORY}",
        "sourceRepositoryDigest": run_identity().source_sha,
        "sourceRepositoryRef": actions.DEFAULT_REF,
        "sourceRepositoryIdentifier": REPO_ID,
        "sourceRepositoryOwnerIdentifier": OWNER_ID,
        "runnerEnvironment": "github-hosted",
        "runInvocationURI": (
            f"https://github.com/{actions.REPOSITORY}/actions/runs/"
            f"{run.run_id}/attempts/{run.run_attempt}"
        ),
    }
    if changed:
        cert.update(changed)
    return [
        {
            "verificationResult": {
                "signature": {"certificate": cert},
                "verifiedTimestamps": [{"type": "Tlog", "timestamp": "2026-09-28T00:00:02Z"}],
                "statement": {
                    "subject": [
                        {
                            "name": "provider-observation.json",
                            "digest": {"sha256": hashlib.sha256(doc_bytes).hexdigest()},
                        }
                    ],
                    "predicateType": "https://slsa.dev/provenance/v1",
                    "predicate": {},
                },
            }
        }
    ]


def make_verifier(
    tmp_path: Path,
    *,
    document: dict[str, Any] | None = None,
    current: dict[str, Any] | None = None,
    changed_cert: dict[str, Any] | None = None,
):
    doc = document or observation()
    path = tmp_path / "provider-observation.json"
    path.write_bytes(actions.canonical_observation_bytes(doc))
    run = run_identity()
    runner = ResultRunner(lambda: verified_attestation(doc, changed=changed_cert))
    api = StaticApi(current)
    verifier = actions.GitHubActionsObservationVerifier(
        path,
        token="test-secret",
        run_identity=run,
        api=api,
        gh_executable="gh-test",
        runner=runner,
    )
    return verifier, path, api, runner


def test_observation_is_bound_to_attestation_run_api_and_exact_target(tmp_path: Path) -> None:
    doc = observation()
    provider = actions.provider_identity(doc, actions.canonical_observation_bytes(doc))
    verifier, _, api, runner = make_verifier(tmp_path, document=doc)

    assert verifier.verify(provider) == actions.GitHubActionsObservationVerifier.name
    assert provider["pull_request"]["base_ref_name"] == "policy"
    assert api.seen_number == 97
    command = runner.calls[0]
    assert "--repo" in command and actions.REPOSITORY in command
    assert "--signer-workflow" in command and actions.SIGNER_WORKFLOW in command
    assert "--signer-digest" in command and WORKFLOW_SHA in command
    assert "--deny-self-hosted-runners" in command
    assert "test-secret" not in " ".join(command)


def test_observation_rejects_target_provider_substitution(tmp_path: Path) -> None:
    doc = observation()
    provider = actions.provider_identity(doc, actions.canonical_observation_bytes(doc))
    target = {
        "provider": "arbitrary-provider",
        "repository": provider["repository"],
        "pull_request": provider["pull_request"],
    }
    verifier, _, _, _ = make_verifier(tmp_path, document=doc)

    with pytest.raises(actions.TrustedObservationError, match="provider observation provider"):
        verifier.verify(target, provider["provider_observation"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("issuer", "https://attacker.example"),
        ("githubWorkflowRepository", "attacker/templates"),
        ("githubWorkflowRef", "refs/heads/pr-branch"),
        ("githubWorkflowSHA", "f" * 40),
        ("buildSignerDigest", "f" * 40),
        ("buildConfigDigest", "f" * 40),
        ("buildTrigger", "pull_request"),
        ("sourceRepositoryDigest", "0" * 40),
        ("sourceRepositoryIdentifier", "999999"),
        ("sourceRepositoryOwnerIdentifier", "999999"),
        ("runnerEnvironment", "self-hosted"),
        (
            "runInvocationURI",
            "https://github.com/TakashiSasaki/templates/actions/runs/other/attempts/1",
        ),
    ],
)
def test_attestation_claim_mismatch_is_rejected(tmp_path: Path, field: str, value: str) -> None:
    doc = observation()
    provider = actions.provider_identity(doc, actions.canonical_observation_bytes(doc))
    verifier, _, _, _ = make_verifier(tmp_path, document=doc, changed_cert={field: value})

    with pytest.raises(actions.TrustedObservationError):
        verifier.verify(provider)


def test_wrong_attested_subject_digest_is_rejected(tmp_path: Path) -> None:
    doc = observation()
    provider = actions.provider_identity(doc, actions.canonical_observation_bytes(doc))
    verifier, _, _, runner = make_verifier(tmp_path, document=doc)

    def wrong_subject():
        value = verified_attestation(doc)
        value[0]["verificationResult"]["statement"]["subject"][0]["digest"]["sha256"] = "0" * 64
        return value

    runner.output_factory = wrong_subject
    with pytest.raises(actions.TrustedObservationError, match="subject digest"):
        verifier.verify(provider)


def test_timestamp_is_not_required_but_ambiguous_attestation_fails_closed(tmp_path: Path) -> None:
    doc = observation()
    provider = actions.provider_identity(doc, actions.canonical_observation_bytes(doc))
    verifier, _, _, runner = make_verifier(tmp_path, document=doc)
    result = verified_attestation(doc)
    result[0]["verificationResult"]["verifiedTimestamps"] = []
    runner.output_factory = lambda: result
    assert verifier.verify(provider) == verifier.name

    runner.output_factory = lambda: verified_attestation(doc) * 2
    with pytest.raises(actions.TrustedObservationError, match="exactly one"):
        verifier.verify(provider)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["repository"].update(id="999999"),
        lambda d: d["repository"].update(name_with_owner="other/repo"),
        lambda d: d["pull_request"].update(id="999999"),
        lambda d: d["pull_request"].update(number=98),
        lambda d: d["pull_request"].update(author_id="9003"),
        lambda d: d["pull_request"]["base"].update(ref="site"),
        lambda d: d["pull_request"]["base"].update(sha="f" * 40),
        lambda d: d["pull_request"]["base"].update(tree="f" * 40),
        lambda d: d["pull_request"]["head"].update(sha="f" * 40),
        lambda d: d["pull_request"]["head"].update(tree="f" * 40),
        lambda d: d["producer"].update(actor_id="9003"),
    ],
)
def test_stale_or_cross_target_live_api_observation_is_rejected(tmp_path: Path, change) -> None:
    doc = observation()
    current = observation()
    change(current)
    provider = actions.provider_identity(doc, actions.canonical_observation_bytes(doc))
    verifier, _, _, _ = make_verifier(tmp_path, document=doc, current=current)

    with pytest.raises(actions.TrustedObservationError, match="stale or differs"):
        verifier.verify(provider)


def test_head_movement_in_handoff_target_is_rejected(tmp_path: Path) -> None:
    doc = observation()
    provider = actions.provider_identity(doc, actions.canonical_observation_bytes(doc))
    provider["pull_request"]["head_ref_oid"] = "f" * 40
    verifier, _, _, _ = make_verifier(tmp_path, document=doc)

    with pytest.raises(actions.TrustedObservationError, match="head commit"):
        verifier.verify(provider)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("repository", "id", "999999"),
        ("repository", "name_with_owner", "other/templates"),
        ("pull_request", "id", "999999"),
        ("pull_request", "node_id", "PR_other"),
        ("pull_request", "number", 98),
        ("pull_request", "base_ref_name", "site"),
        ("pull_request", "base_ref_oid", "f" * 40),
        ("pull_request", "base_tree", "f" * 40),
        ("pull_request", "head_ref_oid", "f" * 40),
        ("pull_request", "head_tree", "f" * 40),
    ],
)
def test_handoff_target_substitution_is_rejected(
    tmp_path: Path, section: str, field: str, value: Any
) -> None:
    doc = observation()
    provider = actions.provider_identity(doc, actions.canonical_observation_bytes(doc))
    provider[section][field] = value
    verifier, _, _, _ = make_verifier(tmp_path, document=doc)

    with pytest.raises(actions.TrustedObservationError):
        verifier.verify(provider)


def test_observation_replay_from_another_run_is_rejected(tmp_path: Path) -> None:
    old_run = actions.ActionsRunIdentity(
        repository=actions.REPOSITORY,
        repository_id=REPO_ID,
        run_id="73123",
        run_attempt=1,
        event="workflow_dispatch",
        ref=actions.DEFAULT_REF,
        workflow_ref=actions.WORKFLOW_REF,
        workflow_sha=WORKFLOW_SHA,
        source_sha="f" * 40,
        actor="maintainer",
        actor_id="9001",
        job="bootstrap",
    )
    doc = observation(old_run)
    provider = actions.provider_identity(doc, actions.canonical_observation_bytes(doc))
    verifier, _, _, _ = make_verifier(tmp_path, document=doc)

    with pytest.raises(actions.TrustedObservationError, match="replayed"):
        verifier.verify(provider)


def test_attestation_command_failure_is_not_converted_to_authentication(tmp_path: Path) -> None:
    doc = observation()
    provider = actions.provider_identity(doc, actions.canonical_observation_bytes(doc))
    verifier, _, _, _ = make_verifier(tmp_path, document=doc)

    def rejected_command(*args: Any, **_kwargs: Any) -> None:
        raise subprocess.CalledProcessError(1, args[0])

    verifier.runner = rejected_command
    with pytest.raises(actions.TrustedObservationError, match="Attestation verification failed"):
        verifier.verify(provider)


@pytest.mark.parametrize(
    "field,value",
    [
        ("GITHUB_REPOSITORY", "attacker/templates"),
        ("GITHUB_REPOSITORY_ID", "999999"),
        ("GITHUB_EVENT_NAME", "pull_request_target"),
        ("GITHUB_REF", "refs/heads/pr-branch"),
        (
            "GITHUB_WORKFLOW_REF",
            "TakashiSasaki/templates/.github/workflows/evil.yml@refs/heads/site",
        ),
        ("GITHUB_WORKFLOW_SHA", "not-a-sha"),
        ("GITHUB_RUN_ATTEMPT", "2"),
        ("TRUSTED_REVIEW_ACTOR_LOGIN", ""),
        ("TRUSTED_REVIEW_ACTOR_LOGIN", "bad/login"),
        ("TRUSTED_REVIEW_ACTOR_ID", "invalid"),
        ("GITHUB_JOB", "another-job"),
    ],
)
def test_workflow_identity_drift_fails_closed(field: str, value: str) -> None:
    env = {
        "GITHUB_REPOSITORY": actions.REPOSITORY,
        "GITHUB_REPOSITORY_ID": REPO_ID,
        "GITHUB_RUN_ID": "73124",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": actions.DEFAULT_REF,
        "GITHUB_WORKFLOW_REF": actions.WORKFLOW_REF,
        "GITHUB_WORKFLOW_SHA": WORKFLOW_SHA,
        "GITHUB_SHA": "f" * 40,
        "TRUSTED_REVIEW_ACTOR_LOGIN": "maintainer",
        "TRUSTED_REVIEW_ACTOR_ID": "9001",
        "GITHUB_JOB": "bootstrap",
    }
    env[field] = value
    with pytest.raises(actions.TrustedObservationError):
        actions.ActionsRunIdentity.from_env(env)


@pytest.mark.parametrize(
    "payload",
    [
        {"authenticated": True},
        {"schema_version": 1, "provider": "github", "authenticated": True},
        {
            "schema_version": 1,
            "provider": "github",
            "repository": {},
            "pull_request": {},
            "observation": {},
            "producer": {},
            "extra": 1,
        },
    ],
)
def test_forged_or_extended_observation_document_is_rejected(payload: dict[str, Any]) -> None:
    with pytest.raises(actions.TrustedObservationError):
        actions.validate_observation(payload)


def test_caller_claim_and_legacy_adapter_name_cannot_authenticate_production() -> None:
    identity = {
        "name": "github",
        "repository": {"id": REPO_ID, "name_with_owner": actions.REPOSITORY},
        "pull_request": {"id": "81001", "number": 97},
        "observation_evidence": {"source": "github_artifact_attestation", "authenticated": True},
    }
    with pytest.raises(ValueError, match="production GitHub Actions verifier"):
        handoff.validate_provider_identity(identity)

    legacy = copy.deepcopy(identity)
    legacy["observation_evidence"]["source"] = "github_authenticated_adapter"
    with pytest.raises(ValueError, match="cannot self-assert authenticated"):
        handoff.validate_provider_identity(legacy)


def test_provider_observation_bytes_reject_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    verifier = actions.GitHubActionsObservationVerifier(
        path,
        token="token",
        run_identity=run_identity(),
        api=StaticApi(),
        runner=ResultRunner(lambda: []),
    )
    with pytest.raises(actions.TrustedObservationError):
        verifier.verify_target({}, {})


def test_api_client_reads_fork_head_tree_without_shell_or_input_interpolation() -> None:
    run = run_identity()
    base_commit = {"sha": BASE_SHA, "tree": {"sha": BASE_TREE}}
    head_commit = {"sha": HEAD_SHA, "tree": {"sha": HEAD_TREE}}
    responses = {
        "/repos/TakashiSasaki/templates": {
            "id": int(REPO_ID),
            "full_name": actions.REPOSITORY,
            "owner": {"id": int(OWNER_ID)},
        },
        "/repos/TakashiSasaki/templates/pulls/97": {
            "id": 81001,
            "node_id": "PR_kwDOExample",
            "number": 97,
            "state": "open",
            "user": {"id": 9002, "login": "contributor"},
            "base": {"ref": "policy", "sha": BASE_SHA, "repo": {"id": int(REPO_ID)}},
            "head": {"sha": HEAD_SHA, "repo": {"full_name": "fork-owner/templates"}},
        },
        f"/repos/TakashiSasaki/templates/git/commits/{BASE_SHA}": base_commit,
        f"/repos/fork-owner/templates/git/commits/{HEAD_SHA}": head_commit,
    }
    requests: list[Any] = []

    class Response:
        def __init__(self, body: dict[str, Any]) -> None:
            self.body = json.dumps(body).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return self.body

    def opener(request, timeout):
        assert timeout == 20
        requests.append(request)
        path = request.full_url.removeprefix(actions.GITHUB_API)
        return Response(responses[path])

    api = actions.GitHubApi("secret-token", opener=opener)
    result = api.observe(97, run)
    assert result["pull_request"]["base"] == {
        "ref": "policy",
        "sha": BASE_SHA,
        "tree": BASE_TREE,
    }
    assert result["pull_request"]["head"] == {"sha": HEAD_SHA, "tree": HEAD_TREE}
    assert requests[-1].full_url.endswith(f"/repos/fork-owner/templates/git/commits/{HEAD_SHA}")
    assert requests[0].get_header("Authorization") == "Bearer secret-token"


def test_api_client_rejects_pull_request_targeting_non_policy_branch() -> None:
    class NonPolicyBaseApi(actions.GitHubApi):
        def get(self, path: str) -> dict[str, Any]:
            if path == "/repos/TakashiSasaki/templates":
                return {
                    "id": int(REPO_ID),
                    "full_name": actions.REPOSITORY,
                    "owner": {"id": int(OWNER_ID)},
                }
            if path == "/repos/TakashiSasaki/templates/pulls/97":
                return {
                    "id": 81001,
                    "node_id": "PR_kwDOExample",
                    "number": 97,
                    "state": "open",
                    "user": {"id": 9002, "login": "contributor"},
                    "base": {
                        "ref": "site",
                        "sha": BASE_SHA,
                        "repo": {"id": int(REPO_ID)},
                    },
                    "head": {
                        "sha": HEAD_SHA,
                        "repo": {"full_name": "fork-owner/templates"},
                    },
                }
            raise AssertionError(f"unexpected GitHub API request: {path}")

    with pytest.raises(actions.TrustedObservationError, match="base ref is not"):
        NonPolicyBaseApi("secret-token").observe(97, run_identity())


def test_pull_request_author_cannot_dispatch_their_own_review() -> None:
    run = replace(run_identity(), actor_id="9002", actor="contributor")

    class AuthorApi(actions.GitHubApi):
        def get(self, path: str) -> dict[str, Any]:
            if path == "/repos/TakashiSasaki/templates":
                return {
                    "id": int(REPO_ID),
                    "full_name": actions.REPOSITORY,
                    "owner": {"id": int(OWNER_ID)},
                }
            if path == "/repos/TakashiSasaki/templates/pulls/97":
                return {
                    "id": 81001,
                    "node_id": "PR_kwDOExample",
                    "number": 97,
                    "state": "open",
                    "user": {"id": 9002, "login": "contributor"},
                }
            raise AssertionError(f"unexpected GitHub API request: {path}")

    with pytest.raises(actions.TrustedObservationError, match="cannot dispatch an independent"):
        AuthorApi("token").observe(97, run)

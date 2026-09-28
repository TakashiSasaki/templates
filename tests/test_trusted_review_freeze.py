from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import prepare_trusted_review_handoff as handoff_module
from scripts import trusted_review_actions as actions
from scripts import trusted_review_freeze as freeze
from scripts import trusted_review_freeze_provider as provider
from scripts.trusted_review_actions import ActionsRunIdentity

REPO_ID = "1315875002"
OWNER_ID = "556958"
WORKFLOW_SHA = "a" * 40
SOURCE_SHA = "b" * 40
BASE_SHA = "c" * 40
BASE_TREE = "d" * 40
HEAD_SHA = "e" * 40
HEAD_TREE = "f" * 40
OBSERVATION_SHA = "1" * 64
IMAGE_SHA = "2" * 64


def run_identity(*, actor: str = "maintainer") -> ActionsRunIdentity:
    return ActionsRunIdentity(
        repository="TakashiSasaki/templates",
        repository_id=REPO_ID,
        run_id="73124",
        run_attempt=1,
        event="workflow_dispatch",
        ref="refs/heads/site",
        workflow_ref=(
            "TakashiSasaki/templates/.github/workflows/trusted-review-bootstrap.yml@refs/heads/site"
        ),
        workflow_sha=WORKFLOW_SHA,
        source_sha=SOURCE_SHA,
        actor=actor,
        actor_id="9001",
        job="bootstrap",
    )


def evidence(*, producer_actor: str = "maintainer") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "provider": "github-actions-ghcr",
        "object": {
            "registry": "ghcr.io",
            "repository": freeze.OCI_REPOSITORY,
            "manifest_digest": f"sha256:{IMAGE_SHA}",
            "media_type": "application/vnd.oci.image.manifest.v1+json",
        },
        "attestation": {
            "digest": f"sha256:{IMAGE_SHA}",
            "issuer": "https://token.actions.githubusercontent.com",
            "repository_id": REPO_ID,
            "owner_id": OWNER_ID,
            "workflow_ref": run_identity().workflow_ref,
            "workflow_sha": WORKFLOW_SHA,
            "source_sha": SOURCE_SHA,
            "run_id": "73124",
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "actor_id": "9001",
            "actor_login": producer_actor,
            "job": "bootstrap",
        },
        "target": {
            "repository_id": REPO_ID,
            "repository_name": "TakashiSasaki/templates",
            "pull_request_id": "81001",
            "pull_request_node_id": "PR_kwDOExample",
            "pull_request_number": 97,
            "base_ref_name": "policy",
            "base_sha": BASE_SHA,
            "base_tree": BASE_TREE,
            "head_sha": HEAD_SHA,
            "head_tree": HEAD_TREE,
            "observation_sha256": OBSERVATION_SHA,
        },
        "roles": [
            {
                "role": "bootstrap_run_image",
                "path": "roles/bootstrap_run_image",
                "inventory_sha256": "3" * 64,
                "identity": {
                    "installer_repository": "TakashiSasaki/templates",
                    "installer_revision": BASE_SHA,
                    "installer_path": "skills/agent-policy",
                    "installer_blob_sha": BASE_TREE,
                    "installer_sha256": "4" * 64,
                    "installation_attestation_sha256": "5" * 64,
                },
            },
            {
                "role": "trusted_base_snapshot",
                "path": "roles/trusted_base_snapshot",
                "inventory_sha256": "6" * 64,
                "identity": {"base_sha": BASE_SHA, "base_tree": BASE_TREE},
            },
            {
                "role": "runtime_image",
                "path": "roles/runtime_image",
                "inventory_sha256": "7" * 64,
                "identity": {
                    "toolchain_repository": "TakashiSasaki/templates",
                    "toolchain_revision": BASE_SHA,
                    "lock_sha256": "8" * 64,
                    "runtime_attestation_sha256": "9" * 64,
                },
            },
            {
                "role": "review_bundle",
                "path": "roles/review_bundle",
                "inventory_sha256": "a" * 64,
                "identity": {
                    "manifest_sha256": "b" * 64,
                    "procedure_skill_sha256": "c" * 64,
                    "semantic_policy_sha256": "d" * 64,
                },
            },
        ],
        "post_freeze_verification": {
            "result": "PASS",
            "before_use": "PASS",
            "after_use": "PASS",
            "verifier": freeze.GitHubActionsOciFreezeVerifier.name,
        },
    }


def role_evidence(
    *,
    role: str = "trusted_base_snapshot",
    target_pr_id: str = "81001",
    manifest_digest: str | None = None,
    producer_actor: str = "maintainer",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "provider": "github-actions-ghcr-role",
        "object": {
            "repository": freeze.OCI_REPOSITORY,
            "manifest_digest": manifest_digest or f"sha256:{IMAGE_SHA}",
            "media_type": "application/vnd.oci.image.manifest.v1+json",
        },
        "attestation": {
            "issuer": "https://token.actions.githubusercontent.com",
            "repository_id": REPO_ID,
            "owner_id": OWNER_ID,
            "workflow_ref": run_identity().workflow_ref,
            "workflow_sha": WORKFLOW_SHA,
            "source_sha": SOURCE_SHA,
            "run_id": "73124",
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "actor_id": "9001",
            "actor_login": producer_actor,
            "job": "bootstrap",
        },
        "target": {
            "repository_id": REPO_ID,
            "repository_name": "TakashiSasaki/templates",
            "pull_request_id": target_pr_id,
            "pull_request_node_id": "PR_kwDOExample",
            "pull_request_number": 97,
            "base_ref_name": "policy",
            "base_sha": BASE_SHA,
            "base_tree": BASE_TREE,
            "head_sha": HEAD_SHA,
            "head_tree": HEAD_TREE,
            "observation_sha256": OBSERVATION_SHA,
        },
        "role": {
            "name": role,
            "path": f"roles/{role}",
            "inventory_sha256": "6" * 64,
            "identity": {"base_sha": BASE_SHA, "base_tree": BASE_TREE},
        },
    }


def handoff() -> dict[str, Any]:
    return {
        "freeze_evidence": {},
        "target": {
            "repository": {"id": REPO_ID, "name_with_owner": "TakashiSasaki/templates"},
            "pull_request": {
                "id": "81001",
                "node_id": "PR_kwDOExample",
                "number": 97,
                "base_ref_name": "policy",
                "base_ref_oid": BASE_SHA,
                "base_tree": BASE_TREE,
                "head_ref_oid": HEAD_SHA,
                "head_tree": HEAD_TREE,
            },
        },
        "provider_observation": {"observation_sha256": OBSERVATION_SHA},
        "bootstrap_authority": {
            "installer": {
                "repository": "TakashiSasaki/templates",
                "revision": BASE_SHA,
                "path": "skills/agent-policy",
                "git_blob": BASE_TREE,
                "sha256": "4" * 64,
            },
            "installation_attestation": {"sha256": "5" * 64},
        },
        "frozen_bootstrap_image": {"inventory_digest": "3" * 64},
        "frozen_trusted_base": {
            "inventory_digest": "6" * 64,
            "revision": BASE_SHA,
            "tree": BASE_TREE,
        },
        "frozen_runtime": {
            "inventory_digest": "7" * 64,
            "toolchain": {"repository": "TakashiSasaki/templates", "revision": BASE_SHA},
            "lock": {"sha256": "8" * 64},
            "runtime_attestation": {"sha256": "9" * 64},
        },
        "review_authority_bundle": {
            "inventory_digest": "a" * 64,
            "manifest_sha256": "b" * 64,
            "procedure": {"skill_sha256": "c" * 64},
            "semantic": {"sha256": "d" * 64},
        },
        "locators": {
            "bootstrap_run_image": "/authority/roles/bootstrap_run_image",
            "trusted_base_snapshot": "/authority/roles/trusted_base_snapshot",
            "runtime_image": "/authority/roles/runtime_image",
            "review_bundle": "/authority/roles/review_bundle",
        },
        "backing_locators": {
            "bootstrap_run_image": "/authority/.materialized/bootstrap_run_image",
            "trusted_base_snapshot": "/authority/.materialized/trusted_base_snapshot",
            "runtime_image": "/authority/.materialized/runtime_image",
            "review_bundle": "/authority/.materialized/review_bundle",
        },
    }


def freeze_summary(verifier: Any) -> dict[str, Any]:
    document = verifier.document
    return {
        "sha256": verifier.sha256,
        "object": document["object"],
        "attestation": document["attestation"],
        "target": document["target"],
        "roles": document["roles"],
    }


class Runner:
    def __init__(self, *, bad_oci_subject: bool = False, bad_file_subject: bool = False) -> None:
        self.bad_oci_subject = bad_oci_subject
        self.bad_file_subject = bad_file_subject
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> SimpleNamespace:
        self.commands.append(command)
        assert kwargs["check"] is True
        subject = command[3]
        if subject.startswith("oci://"):
            digest = "0" * 64 if self.bad_oci_subject else IMAGE_SHA
        else:
            digest = hashlib.sha256(Path(subject).read_bytes()).hexdigest()
            if self.bad_file_subject:
                digest = "0" * 64
        return SimpleNamespace(stdout=json.dumps([verified_attestation(digest)]))


def verified_attestation(
    subject_sha256: str, *, run_id: str = "73124", run_attempt: int = 1
) -> dict[str, Any]:
    cert_identity = (
        "https://github.com/TakashiSasaki/templates/.github/workflows/"
        "trusted-review-bootstrap.yml@refs/heads/site"
    )
    cert = {
        "subjectAlternativeName": {"type": "URI", "value": cert_identity},
        "issuer": "https://token.actions.githubusercontent.com",
        "githubWorkflowRepository": "TakashiSasaki/templates",
        "githubWorkflowRef": "refs/heads/site",
        "githubWorkflowSHA": WORKFLOW_SHA,
        "buildSignerURI": cert_identity,
        "buildSignerDigest": WORKFLOW_SHA,
        "buildConfigURI": cert_identity,
        "buildConfigDigest": WORKFLOW_SHA,
        "buildTrigger": "workflow_dispatch",
        "githubWorkflowTrigger": "workflow_dispatch",
        "sourceRepositoryURI": "https://github.com/TakashiSasaki/templates",
        "sourceRepositoryDigest": SOURCE_SHA,
        "sourceRepositoryRef": "refs/heads/site",
        "sourceRepositoryIdentifier": REPO_ID,
        "sourceRepositoryOwnerIdentifier": OWNER_ID,
        "runnerEnvironment": "github-hosted",
        "runInvocationURI": f"https://github.com/TakashiSasaki/templates/actions/runs/{run_id}/attempts/{run_attempt}",
    }
    return {
        "verificationResult": {
            "signature": {"certificate": cert},
            "statement": {
                "subject": [{"digest": {"sha256": subject_sha256}}],
            },
        }
    }


def write_evidence(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = tmp_path / "freeze-evidence.json"
    path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")))
    return path


def test_valid_schema_and_duplicate_json_key_rejection(tmp_path: Path) -> None:
    document = evidence()
    freeze.validate_freeze_evidence(document)
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":1,"schema_version":1}')
    with pytest.raises(freeze.TrustedFreezeError, match="duplicate JSON key"):
        freeze.load_freeze_evidence(path)


def test_role_freeze_evidence_accepts_canonical_github_bot_actor() -> None:
    freeze.validate_role_freeze_evidence(role_evidence(producer_actor="github-actions[bot]"))


def test_role_freeze_evidence_is_strict_and_attested_for_exact_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    role = "trusted_base_snapshot"
    document = role_evidence(role=role)
    freeze.validate_role_freeze_evidence(document)
    evidence_path = tmp_path / "role-freeze.json"
    evidence_path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")))

    source = tmp_path / "source" / "trusted-base-snapshot"
    source.mkdir(parents=True)
    (source / "base.txt").write_text("trusted base")
    protected_root = tmp_path / "protected"
    protected = protected_root / "roles" / role
    protected.mkdir(parents=True)
    (protected / "base.txt").write_text("trusted base")
    backing = protected_root / ".materialized" / role
    backing.mkdir(parents=True)
    (backing / "base.txt").write_text("trusted base")
    monkeypatch.setenv("TRUSTED_REVIEW_PROTECTED_ROOT", str(protected_root))
    monkeypatch.setattr(freeze, "require_protected_view", lambda *_args, **_kwargs: None)

    expected_target = {
        "repository": {"id": REPO_ID, "name_with_owner": "TakashiSasaki/templates"},
        "pull_request": {
            "id": "81001",
            "node_id": "PR_kwDOExample",
            "number": 97,
            "base_ref_name": "policy",
            "base_ref_oid": BASE_SHA,
            "base_tree": BASE_TREE,
            "head_ref_oid": HEAD_SHA,
            "head_tree": HEAD_TREE,
        },
        "provider_observation": {"observation_sha256": OBSERVATION_SHA},
    }
    adapter = freeze.GitHubActionsRoleFreezeVerifier(
        evidence_path,
        expected_target,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(),
    )
    inventory = freeze._inventory_digest(source)
    doc = adapter.document
    doc["role"]["inventory_sha256"] = inventory
    evidence_path.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")))
    adapter = freeze.GitHubActionsRoleFreezeVerifier(
        evidence_path,
        expected_target,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(),
    )
    marker = handoff_freeze_marker(adapter)
    actual = adapter.verify_freeze(
        role,
        source,
        marker,
        expected_inventory_sha256=inventory,
        backing_path=backing,
        expected_identity={"base_sha": BASE_SHA, "base_tree": BASE_TREE},
    )
    assert actual == protected


def handoff_freeze_marker(adapter: Any) -> Any:
    from scripts.prepare_trusted_review_handoff import FreezeBoundaryType, FreezeEvidence

    return FreezeEvidence(
        boundary_type=FreezeBoundaryType.DEPLOYMENT_ESTABLISHED,
        mechanism=f"{adapter.name}:{adapter.document['object']['manifest_digest']}",
        evidence_status="authenticated",
        attestation_sha256=adapter.sha256,
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda value: value["role"].update(name="review_bundle"), "different artifact role"),
        (
            lambda value: value["target"].update(pull_request_id="81002"),
            "another repository or pull request",
        ),
        (lambda value: value["attestation"].update(actor_id="9002"), "workflow identity"),
        (
            lambda value: value["object"].update(manifest_digest="sha256:" + "f" * 64),
            "subject digest",
        ),
    ],
)
def test_role_freeze_evidence_rejects_role_target_actor_and_digest_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change,
    message: str,
) -> None:
    document = role_evidence()
    source = tmp_path / "source"
    source.mkdir()
    (source / "base.txt").write_text("trusted base")
    inventory = freeze._inventory_digest(source)
    document["role"]["inventory_sha256"] = inventory
    change(document)
    evidence_path = tmp_path / "role-freeze.json"
    evidence_path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")))
    protected_root = tmp_path / "protected"
    protected = protected_root / "roles" / "trusted_base_snapshot"
    protected.mkdir(parents=True)
    (protected / "base.txt").write_text("trusted base")
    monkeypatch.setenv("TRUSTED_REVIEW_PROTECTED_ROOT", str(protected_root))
    monkeypatch.setattr(freeze, "require_protected_view", lambda *_args, **_kwargs: None)
    expected_target = {
        "repository": {"id": REPO_ID, "name_with_owner": "TakashiSasaki/templates"},
        "pull_request": {
            "id": "81001",
            "node_id": "PR_kwDOExample",
            "number": 97,
            "base_ref_name": "policy",
            "base_ref_oid": BASE_SHA,
            "base_tree": BASE_TREE,
            "head_ref_oid": HEAD_SHA,
            "head_tree": HEAD_TREE,
        },
        "provider_observation": {"observation_sha256": OBSERVATION_SHA},
    }
    adapter = freeze.GitHubActionsRoleFreezeVerifier(
        evidence_path,
        expected_target,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(),
    )
    marker = handoff_freeze_marker(adapter)
    with pytest.raises(freeze.TrustedFreezeError, match=message):
        adapter.verify_freeze(
            "trusted_base_snapshot",
            source,
            marker,
            expected_inventory_sha256=inventory,
            backing_path=tmp_path / "protected" / ".materialized" / "trusted_base_snapshot",
            expected_identity={"base_sha": BASE_SHA, "base_tree": BASE_TREE},
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["attestation"].update(repository_id="999999"),
        lambda value: value["object"].update(media_type="application/vnd.oci.image.index.v1+json"),
        lambda value: value["roles"].append(value["roles"][0]),
        lambda value: value["roles"][1].update(path="roles/runtime_image"),
        lambda value: value["post_freeze_verification"].update(after_use="FAIL"),
        lambda value: value["target"].pop("base_ref_name"),
        lambda value: value["target"].update(base_ref_name="site"),
    ],
)
def test_schema_rejects_mismatched_target_or_freeze_identity(mutate: Any) -> None:
    document = evidence()
    mutate(document)
    with pytest.raises(freeze.TrustedFreezeError):
        freeze.validate_freeze_evidence(document)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["target"].pop("base_ref_name"),
        lambda value: value["target"].update(base_ref_name="site"),
    ],
)
def test_role_freeze_schema_requires_the_policy_base_ref(mutate: Any) -> None:
    document = role_evidence()
    mutate(document)
    with pytest.raises(freeze.TrustedFreezeError):
        freeze.validate_role_freeze_evidence(document)


def test_aggregate_freeze_verifier_uses_the_recorded_sibling_backing_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protected_root = tmp_path / "aggregate-protected"
    sibling_root = tmp_path / ".aggregate-protected.materialized"
    observed: list[Path] = []

    class StaticVerifier:
        name = "test-role-freeze"
        sha256 = "a" * 64
        document = {"object": {"manifest_digest": "sha256:" + "b" * 64}}

        def __init__(self, _path: Path, _provider_identity: dict[str, Any]) -> None:
            pass

        def verify_freeze(
            self,
            _role: str,
            exposed_path: Path,
            _evidence: Any,
            *,
            backing_path: Path,
            expected_inventory_sha256: str,
            expected_identity: dict[str, Any],
        ) -> Path:
            assert expected_inventory_sha256
            assert expected_identity == {}
            observed.append(Path(backing_path))
            return Path(exposed_path).resolve()

    monkeypatch.setenv("TRUSTED_REVIEW_PROTECTED_ROOT", str(protected_root))
    monkeypatch.setattr(provider, "GitHubActionsRoleFreezeVerifier", StaticVerifier)
    monkeypatch.setattr(provider, "expected_freeze_role_identity", lambda *_args, **_kwargs: {})
    state = {
        "artifacts": {
            role: {
                "locator": str(protected_root / "roles" / role),
                "backing_locator": str(sibling_root / role),
                "materialized_digest": "c" * 64,
            }
            for role in provider.ROLE_NAMES
        }
    }

    provider._verify_protected_role_evidence(
        state,
        {},
        tmp_path / "installation-attestation.json",
        tmp_path / "role-evidence",
    )

    assert observed == [sibling_root / role for role in provider.ROLE_NAMES]


def test_protected_role_backing_locator_rejects_a_non_sibling_path(tmp_path: Path) -> None:
    protected_root = tmp_path / "aggregate-protected"
    with pytest.raises(provider.TrustedFreezeError, match="recorded sibling tree"):
        provider._protected_role_backing_path(
            protected_root,
            "runtime_image",
            {"backing_locator": str(tmp_path / "unrelated")},
        )


def test_freeze_verifier_binds_handoff_and_attested_image(tmp_path: Path) -> None:
    document = evidence()
    path = write_evidence(tmp_path, document)
    runner = Runner()
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        path,
        token="test-token",
        run_identity=run_identity(),
        runner=runner,
    )
    data = handoff()
    data["freeze_evidence"] = freeze_summary(verifier)

    verifier.verify_document_digest(data)

    assert verifier.production_capable is False
    assert len(runner.commands) == 2
    assert "--bundle-from-oci" not in runner.commands[0]
    assert str(path) in runner.commands[0]
    assert "--bundle-from-oci" in runner.commands[1]
    assert f"oci://{freeze.OCI_REPOSITORY}@sha256:{IMAGE_SHA}" in runner.commands[1]


def test_freeze_evidence_cannot_be_replayed_to_another_pull_request(tmp_path: Path) -> None:
    document = evidence()
    path = write_evidence(tmp_path, document)
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        path,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(),
    )
    data = handoff()
    data["target"]["pull_request"]["number"] = 98
    data["freeze_evidence"] = freeze_summary(verifier)
    with pytest.raises(freeze.TrustedFreezeError, match="pull_request_number"):
        verifier.verify_document_digest(data)


def test_freeze_evidence_cannot_be_replayed_from_another_workflow_source(
    tmp_path: Path,
) -> None:
    document = evidence()
    document["attestation"]["source_sha"] = "e" * 40
    path = write_evidence(tmp_path, document)
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        path,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(),
    )
    data = handoff()
    data["freeze_evidence"] = freeze_summary(verifier)
    with pytest.raises(freeze.TrustedFreezeError, match="workflow identity"):
        verifier.verify_document_digest(data)


def test_freeze_verifier_fails_closed_on_bad_attestation(tmp_path: Path) -> None:
    document = evidence()
    path = write_evidence(tmp_path, document)
    runner = Runner(bad_oci_subject=True)
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        path, token="test-token", run_identity=run_identity(), runner=runner
    )
    data = handoff()
    data["freeze_evidence"] = freeze_summary(verifier)
    with pytest.raises(freeze.TrustedFreezeError, match="subject digest"):
        verifier.verify_document_digest(data)


def test_attestation_verifier_selects_the_current_run_for_repeated_subjects() -> None:
    old_run = verified_attestation(IMAGE_SHA, run_id="71000")
    current_run = verified_attestation(IMAGE_SHA)

    def runner(_command: list[str], **kwargs: Any) -> SimpleNamespace:
        assert kwargs["check"] is True
        return SimpleNamespace(stdout=json.dumps([old_run, current_run]))

    freeze._verify_subject_attestation(
        f"oci://{freeze.OCI_REPOSITORY}@sha256:{IMAGE_SHA}",
        IMAGE_SHA,
        run_identity=run_identity(),
        owner_id=OWNER_ID,
        gh_executable="/usr/bin/gh",
        runner=runner,
        use_oci_bundle=True,
    )


@pytest.mark.parametrize(
    "results",
    [
        [verified_attestation(IMAGE_SHA, run_id="71000")],
        [verified_attestation(IMAGE_SHA), verified_attestation(IMAGE_SHA)],
    ],
)
def test_attestation_verifier_requires_one_current_run_result(
    results: list[dict[str, Any]],
) -> None:
    def runner(_command: list[str], **kwargs: Any) -> SimpleNamespace:
        assert kwargs["check"] is True
        return SimpleNamespace(stdout=json.dumps(results))

    with pytest.raises(
        freeze.TrustedFreezeError,
        match="exactly one result for this workflow run",
    ):
        freeze._verify_subject_attestation(
            f"oci://{freeze.OCI_REPOSITORY}@sha256:{IMAGE_SHA}",
            IMAGE_SHA,
            run_identity=run_identity(),
            owner_id=OWNER_ID,
            gh_executable="/usr/bin/gh",
            runner=runner,
            use_oci_bundle=True,
        )


def test_freeze_evidence_requires_its_own_attestation(tmp_path: Path) -> None:
    path = write_evidence(tmp_path, evidence())
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        path,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(bad_file_subject=True),
    )
    data = handoff()
    data["freeze_evidence"] = freeze_summary(verifier)
    with pytest.raises(freeze.TrustedFreezeError, match="subject digest"):
        verifier.verify_document_digest(data)


def test_freeze_evidence_mutation_after_load_is_rejected(tmp_path: Path) -> None:
    path = write_evidence(tmp_path, evidence())
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        path,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(),
    )
    path.write_text("{}")
    with pytest.raises(freeze.TrustedFreezeError, match="changed during use"):
        verifier.verify_document_digest(handoff())


def test_protected_view_rejects_writable_mount(tmp_path: Path) -> None:
    role = tmp_path / "roles" / "review_bundle"
    role.mkdir(parents=True)
    with pytest.raises(freeze.TrustedFreezeError, match="read-only filesystem"):
        freeze.require_protected_view(role)


def test_protected_view_rejects_writable_backing_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = tmp_path / "protected" / "review_bundle"
    backing = tmp_path / "materialized" / "review_bundle"
    view.mkdir(parents=True)
    backing.mkdir(parents=True)
    monkeypatch.setattr(
        freeze.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_flag=getattr(freeze.os, "ST_RDONLY", 1)),
    )
    monkeypatch.setattr(
        freeze,
        "_readonly_mount",
        lambda path, _mountinfo=None: Path(path) != backing,
    )
    monkeypatch.setattr(freeze.os.path, "samefile", lambda _left, _right: True)

    with pytest.raises(freeze.TrustedFreezeError, match="read-only filesystem"):
        freeze.require_protected_view(view, backing_path=backing)


def test_protected_view_requires_the_declared_backing_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = tmp_path / "protected" / "review_bundle"
    backing = tmp_path / "materialized" / "review_bundle"
    view.mkdir(parents=True)
    backing.mkdir(parents=True)
    monkeypatch.setattr(
        freeze.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_flag=getattr(freeze.os, "ST_RDONLY", 1)),
    )
    monkeypatch.setattr(freeze, "_readonly_mount", lambda _path, _mountinfo=None: True)
    monkeypatch.setattr(freeze.os.path, "samefile", lambda _left, _right: False)

    with pytest.raises(freeze.TrustedFreezeError, match="declared backing tree"):
        freeze.require_protected_view(view, backing_path=backing)


def test_role_verification_rejects_writable_backing_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = evidence()
    role = next(item for item in document["roles"] if item["role"] == "review_bundle")
    root = tmp_path / "authority"
    view = root / role["path"]
    backing = root / ".materialized" / "review_bundle"
    view.mkdir(parents=True)
    backing.mkdir(parents=True)
    (view / "authority.txt").write_text("review bundle")
    (backing / "authority.txt").write_text("review bundle")
    role["inventory_sha256"] = freeze._inventory_digest(view)

    data = handoff()
    data["locators"]["review_bundle"] = str(view)
    data["backing_locators"]["review_bundle"] = str(backing)
    data["review_authority_bundle"]["inventory_digest"] = role["inventory_sha256"]
    evidence_path = write_evidence(tmp_path, document)
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        evidence_path,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(),
    )
    data["freeze_evidence"] = freeze_summary(verifier)
    verifier.verify_document_digest(data)

    monkeypatch.setattr(
        freeze.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_flag=getattr(freeze.os, "ST_RDONLY", 1)),
    )
    monkeypatch.setattr(
        freeze,
        "_readonly_mount",
        lambda path, _mountinfo=None: Path(path).absolute() != backing.absolute(),
    )

    with pytest.raises(freeze.TrustedFreezeError, match="read-only filesystem"):
        verifier.verify("review_authority_bundle", data["review_authority_bundle"])


def test_readonly_backing_and_view_reject_transient_alias_writes(tmp_path: Path) -> None:
    if os.name != "posix" or shutil.which("sudo") is None:
        pytest.skip("Linux bind-mount permissions are unavailable")

    protected_root = tmp_path / "protected"
    backing = protected_root / ".materialized" / "review_bundle"
    view = protected_root / "roles" / "review_bundle"
    backing.mkdir(parents=True)
    view.mkdir(parents=True)
    authority = backing / "authority.txt"
    authority.write_text("frozen authority\n", encoding="utf-8")
    mounted: list[Path] = []

    def mount(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sudo", "-n", "mount", *args], capture_output=True, text=True, check=False
        )

    try:
        bind = mount("--bind", str(backing), str(backing))
        if bind.returncode:
            pytest.skip(f"kernel denied bind mounts: {(bind.stderr or bind.stdout).strip()}")
        mounted.append(backing)

        remount = mount("-o", "remount,bind,ro", str(backing))
        assert remount.returncode == 0, remount.stderr or remount.stdout
        freeze.require_protected_view(backing)

        exposed = mount("--bind", str(backing), str(view))
        assert exposed.returncode == 0, exposed.stderr or exposed.stdout
        mounted.append(view)
        readonly = mount("-o", "remount,bind,ro", str(view))
        assert readonly.returncode == 0, readonly.stderr or readonly.stdout
        freeze.require_protected_view(view, backing_path=backing)

        original = authority.read_bytes()
        for alias in (backing / "authority.txt", view / "authority.txt"):
            with pytest.raises(OSError):
                alias.write_text("transient attack\n", encoding="utf-8")
        assert authority.read_bytes() == original
        assert (view / "authority.txt").read_bytes() == original
    finally:
        for mountpoint in reversed(mounted):
            unmount = subprocess.run(
                ["sudo", "-n", "umount", str(mountpoint)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert unmount.returncode == 0, unmount.stderr or unmount.stdout


def test_readonly_mount_parser_uses_most_specific_mount(tmp_path: Path) -> None:
    role = tmp_path / "root" / "authority"
    role.mkdir(parents=True)
    mountinfo = (
        "30 20 0:1 / / rw,relatime - overlay overlay rw\n"
        f"31 30 0:2 / {role.parent} ro,relatime - tmpfs tmpfs ro\n"
    )
    assert freeze._readonly_mount(role, mountinfo)


def test_inventory_rejects_symlink_and_hardlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "authority.txt"
    target.write_text("authority")
    link = root / "link"
    link.symlink_to(target)
    with pytest.raises(freeze.TrustedFreezeError, match="symbolic link"):
        freeze._inventory_digest(root)
    link.unlink()

    duplicate = root / "duplicate.txt"
    os.link(target, duplicate)
    with pytest.raises(freeze.TrustedFreezeError, match="hard link"):
        freeze._inventory_digest(root)


def test_post_use_verification_requires_all_four_roles(tmp_path: Path) -> None:
    path = write_evidence(tmp_path, evidence())
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        path,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(),
    )
    with pytest.raises(freeze.TrustedFreezeError, match="all four"):
        verifier.verify_post_use(handoff())


def test_authority_mutation_between_pre_and_post_use_checks_is_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "authority"
    locators: dict[str, str] = {}
    doc = evidence()
    handoff_data = handoff()
    for role in doc["roles"]:
        role_path = root / role["path"]
        role_path.mkdir(parents=True)
        payload = role_path / "authority.txt"
        payload.write_text(role["role"])
        role["inventory_sha256"] = freeze._inventory_digest(role_path)
        locator_key = freeze.SECTION_TO_LOCATOR[role["role"]]
        locators[locator_key] = str(role_path)
        section = freeze.ROLE_TO_SECTION[role["role"]]
        if section == "frozen_bootstrap_image":
            handoff_data[section]["inventory_digest"] = role["inventory_sha256"]
        elif section == "frozen_trusted_base":
            handoff_data[section]["inventory_digest"] = role["inventory_sha256"]
        elif section == "frozen_runtime":
            handoff_data[section]["inventory_digest"] = role["inventory_sha256"]
        else:
            handoff_data[section]["inventory_digest"] = role["inventory_sha256"]
    handoff_data["locators"].update(locators)
    handoff_data["backing_locators"] = dict(locators)
    evidence_path = write_evidence(tmp_path, doc)
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        evidence_path,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(),
    )
    handoff_data["freeze_evidence"] = freeze_summary(verifier)
    monkeypatch.setattr(freeze, "require_protected_view", lambda *_args, **_kwargs: None)
    verifier.verify_document_digest(handoff_data)
    for _role, section in freeze.ROLE_TO_SECTION.items():
        verifier.verify(section, handoff_data[section])

    (root / "roles/review_bundle/authority.txt").write_text("mutated")
    with pytest.raises(freeze.TrustedFreezeError, match="inventory changed"):
        verifier.verify_post_use(handoff_data)


def _portable_observation(*, producer_actor: str = "maintainer") -> dict[str, Any]:
    run = run_identity(actor=producer_actor)
    return {
        "schema_version": 1,
        "provider": "github",
        "repository": {"id": REPO_ID, "name_with_owner": "TakashiSasaki/templates"},
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
            "run_id": run.run_id,
            "run_attempt": run.run_attempt,
            "event": run.event,
        },
        "producer": {
            "issuer": actions.OIDC_ISSUER,
            "repository_id": run.repository_id,
            "owner_id": actions.OWNER_ID,
            "workflow_ref": run.workflow_ref,
            "workflow_sha": run.workflow_sha,
            "source_sha": run.source_sha,
            "actor_id": run.actor_id,
            "actor_login": run.actor,
            "job": run.job,
        },
    }


def _portable_handoff_fixture(
    tmp_path: Path, *, producer_actor: str = "maintainer"
) -> dict[str, Any]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    observation = _portable_observation(producer_actor=producer_actor)
    observation_raw = actions.canonical_observation_bytes(observation)
    observation_path = tmp_path / "provider-observation.json"
    observation_path.write_bytes(observation_raw)
    observation_sha = hashlib.sha256(observation_raw).hexdigest()

    role_root = tmp_path / "oci-roles"
    role_files = {
        "bootstrap_run_image": {"bootstrap.py": b"bootstrap\n"},
        "trusted_base_snapshot": {"policy.yml": b"policy\n"},
        "runtime_image": {"runtime.py": b"runtime\n"},
        "review_bundle": {
            "manifest.json": b"{}\n",
            "procedure/SKILL.md": b"review skill\n",
            "semantic/review-policy.md": b"review policy\n",
        },
    }
    role_paths: dict[str, Path] = {}
    for role, files in role_files.items():
        directory = role_root / role
        for relative, payload in files.items():
            path = directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        role_paths[role] = directory

    document = evidence(producer_actor=producer_actor)
    document["target"]["observation_sha256"] = observation_sha
    records = {item["role"]: item for item in document["roles"]}
    for role, directory in role_paths.items():
        records[role]["inventory_sha256"] = freeze._inventory_digest(directory)
    bundle_identity = records["review_bundle"]["identity"]
    bundle_identity["manifest_sha256"] = hashlib.sha256(
        (role_paths["review_bundle"] / "manifest.json").read_bytes()
    ).hexdigest()
    bundle_identity["procedure_skill_sha256"] = hashlib.sha256(
        (role_paths["review_bundle"] / "procedure/SKILL.md").read_bytes()
    ).hexdigest()
    bundle_identity["semantic_policy_sha256"] = hashlib.sha256(
        (role_paths["review_bundle"] / "semantic/review-policy.md").read_bytes()
    ).hexdigest()
    freeze.validate_freeze_evidence(document)
    evidence_raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    evidence_path = tmp_path / "freeze-evidence.json"
    evidence_path.write_bytes(evidence_raw)
    evidence_sha = hashlib.sha256(evidence_raw).hexdigest()

    def mechanism() -> dict[str, str]:
        return {
            "boundary_type": "deployment_established",
            "mechanism": freeze.GitHubActionsOciFreezeVerifier.name,
            "evidence_status": "authenticated",
            "verifier": freeze.GitHubActionsOciFreezeVerifier.name,
        }

    bundle_record = records["review_bundle"]
    handoff_data: dict[str, Any] = {
        "schema_version": 1,
        "handoff_type": "AUTHENTICATED_IMMUTABLE_REVIEW_BOOTSTRAP_HANDOFF",
        "target": {
            "provider": "github",
            "repository": {"id": REPO_ID, "name_with_owner": "TakashiSasaki/templates"},
            "pull_request": {
                "id": "81001",
                "node_id": "PR_kwDOExample",
                "number": 97,
                "base_ref_name": "policy",
                "base_ref_oid": BASE_SHA,
                "base_tree": BASE_TREE,
                "head_ref_name": "feature/trusted-review",
                "head_ref_oid": HEAD_SHA,
                "head_tree": HEAD_TREE,
            },
        },
        "provider_observation": {"observation_sha256": observation_sha},
        "bootstrap_authority": {
            "installer": {
                "repository": "TakashiSasaki/templates",
                "revision": BASE_SHA,
                "path": "skills/agent-policy",
                "git_blob": BASE_TREE,
                "blob_sha": BASE_TREE,
                "sha256": "4" * 64,
            },
            "skill_source": {
                "repository": "TakashiSasaki/templates",
                "revision": BASE_SHA,
                "path": "skills/agent-policy",
            },
            "installation_attestation": {"path": "attestation.json", "sha256": "5" * 64},
        },
        "frozen_bootstrap_image": {
            "inventory_digest": records["bootstrap_run_image"]["inventory_sha256"],
            "freeze_mechanism": mechanism(),
            "post_freeze_verification": {"result": "PASS", "verifier": "trusted-freeze"},
        },
        "frozen_trusted_base": {
            "revision": BASE_SHA,
            "tree": BASE_TREE,
            "inventory_digest": records["trusted_base_snapshot"]["inventory_sha256"],
            "freeze_mechanism": mechanism(),
            "post_freeze_verification": {"result": "PASS", "verifier": "trusted-freeze"},
        },
        "frozen_runtime": {
            "toolchain": {"repository": "TakashiSasaki/templates", "revision": BASE_SHA},
            "lock": {"path": ".agent-policy.lock", "sha256": "8" * 64},
            "runtime_attestation": {"path": "runtime-attestation.json", "sha256": "9" * 64},
            "inventory_digest": records["runtime_image"]["inventory_sha256"],
            "freeze_mechanism": mechanism(),
            "post_freeze_verification": {"result": "PASS", "verifier": "trusted-freeze"},
        },
        "trusted_base_validation": {
            "check_command": {"result": "PASS"},
            "validate_command": {"result": "PASS"},
        },
        "review_authority_bundle": {
            "bundle_format": 1,
            "inventory_digest": bundle_record["inventory_sha256"],
            "manifest_sha256": bundle_identity["manifest_sha256"],
            "freeze_mechanism": mechanism(),
            "post_freeze_verification": {"result": "PASS", "verifier": "trusted-freeze"},
            "procedure": {
                "skill_path": "procedure/SKILL.md",
                "skill_sha256": bundle_identity["procedure_skill_sha256"],
                "references": [],
            },
            "semantic": {
                "bundle_path": "semantic/review-policy.md",
                "renderer": "policy-context-md",
                "sha256": bundle_identity["semantic_policy_sha256"],
            },
        },
        "freeze_evidence": {
            "sha256": evidence_sha,
            "object": document["object"],
            "attestation": document["attestation"],
            "target": document["target"],
            "roles": document["roles"],
        },
    }
    handoff_path = tmp_path / "handoff.json"
    handoff_path.write_text(json.dumps(handoff_data, indent=2, sort_keys=True) + "\n")
    return {
        "handoff": handoff_data,
        "handoff_path": handoff_path,
        "observation": observation,
        "observation_path": observation_path,
        "freeze_evidence": document,
        "freeze_evidence_path": evidence_path,
        "role_paths": role_paths,
        "observation_sha": observation_sha,
    }


class HydrationRunner:
    def __init__(
        self,
        role_paths: dict[str, Path],
        *,
        bad_first_attestation: bool = False,
        substitute_role: str | None = None,
    ) -> None:
        self.role_paths = role_paths
        self.bad_first_attestation = bad_first_attestation
        self.substitute_role = substitute_role
        self.attestation_count = 0
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **_kwargs: Any) -> SimpleNamespace:
        self.commands.append(command)
        if command[0] == freeze.GH_EXECUTABLE:
            subject = command[3]
            if subject.startswith("oci://"):
                digest = subject.rsplit("@sha256:", 1)[1]
            else:
                digest = hashlib.sha256(Path(subject).read_bytes()).hexdigest()
            if self.bad_first_attestation and self.attestation_count == 0:
                digest = "0" * 64
            self.attestation_count += 1
            return SimpleNamespace(stdout=json.dumps([verified_attestation(digest)]))
        if command[:2] == ["docker", "create"]:
            return SimpleNamespace(stdout="portable-reviewer-container\n")
        if command[:2] == ["docker", "cp"]:
            role = command[2].split("/roles/", 1)[1].split("/", 1)[0]
            destination = Path(command[-1])
            shutil.copytree(self.role_paths[role], destination, dirs_exist_ok=True)
            if self.substitute_role == role:
                semantic = destination / "semantic/review-policy.md"
                if semantic.exists():
                    semantic.write_text("substituted policy\n", encoding="utf-8")
            return SimpleNamespace(stdout="")
        if command[:3] == ["sudo", "mount", "--bind"]:
            source = Path(command[-2])
            destination = Path(command[-1])
            if source != destination:
                shutil.copytree(source, destination, dirs_exist_ok=True)
            return SimpleNamespace(stdout="")
        return SimpleNamespace(stdout="")


def _install_hydration_test_doubles(
    monkeypatch: pytest.MonkeyPatch,
    fixture: dict[str, Any],
    runner: HydrationRunner,
    *,
    protection_check: Any | None = None,
    use_real_docker_login: bool = False,
) -> list[tuple[Path, Path | None]]:
    observation = fixture["observation"]
    seen_protected_checks: list[tuple[Path, Path | None]] = []

    class StaticApi:
        def observe(self, _number: int, _run: ActionsRunIdentity) -> dict[str, Any]:
            value = json.loads(json.dumps(observation))
            value["observation"]["retrieved_at"] = "2026-09-28T00:00:01Z"
            return value

    def observation_verifier(path: Path, **kwargs: Any) -> Any:
        return actions.GitHubActionsObservationVerifier(path, api=StaticApi(), **kwargs)

    def require_view(path: Path, *, backing_path: Path | None = None, **_kwargs: Any) -> None:
        seen_protected_checks.append((Path(path), backing_path))
        if protection_check is not None:
            protection_check(Path(path), backing_path)

    monkeypatch.setenv("GITHUB_TOKEN", "test-api-token")
    monkeypatch.setenv("GH_TOKEN", "test-gh-token")
    monkeypatch.setenv("GITHUB_ACTOR", fixture["freeze_evidence"]["attestation"]["actor_login"])
    monkeypatch.setattr(provider, "GitHubActionsObservationVerifier", observation_verifier)
    if not use_real_docker_login:
        monkeypatch.setattr(provider, "_docker_login", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        provider,
        "_verify_image_manifest",
        lambda digest, **_kwargs: assert_digest(digest),
    )
    monkeypatch.setattr(provider, "require_protected_view", require_view)
    monkeypatch.setattr(freeze, "require_protected_view", require_view)
    return seen_protected_checks


def assert_digest(digest: str) -> None:
    assert digest == f"sha256:{IMAGE_SHA}"


@pytest.mark.parametrize("producer_actor", ["maintainer", "github-actions[bot]"])
def test_portable_handoff_hydrates_without_producer_locators(
    producer_actor: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _portable_handoff_fixture(tmp_path, producer_actor=producer_actor)
    assert "locators" not in fixture["handoff"]
    runner = HydrationRunner(fixture["role_paths"])
    protected_checks = _install_hydration_test_doubles(
        monkeypatch, fixture, runner, use_real_docker_login=True
    )
    root = tmp_path / "fresh-reviewer"
    local_view_path = tmp_path / "reviewer-local-view.json"

    provider.hydrate_handoff(
        fixture["handoff_path"],
        fixture["observation_path"],
        fixture["freeze_evidence_path"],
        root,
        local_view_path,
        runner=runner,
    )

    local_view = json.loads(local_view_path.read_text(encoding="utf-8"))
    assert local_view["handoff_sha256"] == hashlib.sha256(
        fixture["handoff_path"].read_bytes()
    ).hexdigest()
    assert local_view["provider_observation_sha256"] == fixture["observation_sha"]
    assert local_view["freeze_evidence_sha256"] == fixture["handoff"]["freeze_evidence"]["sha256"]
    assert all(Path(path).is_relative_to(root) for path in local_view["locators"].values())
    assert all(Path(path).is_relative_to(root) for path in local_view["backing_locators"].values())
    assert any(backing is None for _path, backing in protected_checks)
    assert any(backing is not None for _path, backing in protected_checks)
    assert all(
        command[-1].endswith(f"@sha256:{IMAGE_SHA}")
        for command in runner.commands
        if command[:2] == ["docker", "pull"]
    )
    assert [
        "docker",
        "login",
        "ghcr.io",
        "--username",
        producer_actor,
        "--password-stdin",
    ] in runner.commands


def test_portable_handoff_rejects_producer_locators_and_wrong_digest_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _portable_handoff_fixture(tmp_path)
    fixture["handoff"]["locators"] = {"review_bundle": "/producer/runner/path"}
    fixture["handoff_path"].write_text(json.dumps(fixture["handoff"]))
    runner = HydrationRunner(fixture["role_paths"])
    _install_hydration_test_doubles(monkeypatch, fixture, runner)
    with pytest.raises(freeze.TrustedFreezeError, match="producer-local"):
        provider.hydrate_handoff(
            fixture["handoff_path"],
            fixture["observation_path"],
            fixture["freeze_evidence_path"],
            tmp_path / "fresh-reviewer",
            tmp_path / "local-view.json",
            runner=runner,
        )
    assert not any(command[:2] == ["docker", "pull"] for command in runner.commands)

    fixture = _portable_handoff_fixture(tmp_path / "wrong-tag")
    evidence_data = fixture["freeze_evidence"]
    evidence_data["object"]["manifest_digest"] += ":latest"
    evidence_data["attestation"]["digest"] = evidence_data["object"]["manifest_digest"]
    fixture["freeze_evidence_path"].write_text(json.dumps(evidence_data))
    runner = HydrationRunner(fixture["role_paths"])
    _install_hydration_test_doubles(monkeypatch, fixture, runner)
    with pytest.raises(freeze.TrustedFreezeError):
        provider.hydrate_handoff(
            fixture["handoff_path"],
            fixture["observation_path"],
            fixture["freeze_evidence_path"],
            tmp_path / "wrong-tag" / "fresh-reviewer",
            tmp_path / "wrong-tag" / "local-view.json",
            runner=runner,
        )
    assert not any(command[:2] == ["docker", "pull"] for command in runner.commands)


def test_portable_hydration_rejects_forged_attestation_missing_oci_and_role_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _portable_handoff_fixture(tmp_path / "forged")
    runner = HydrationRunner(fixture["role_paths"], bad_first_attestation=True)
    _install_hydration_test_doubles(monkeypatch, fixture, runner)
    with pytest.raises(freeze.TrustedFreezeError, match="subject digest"):
        provider.hydrate_handoff(
            fixture["handoff_path"],
            fixture["observation_path"],
            fixture["freeze_evidence_path"],
            tmp_path / "forged" / "fresh-reviewer",
            tmp_path / "forged" / "local-view.json",
            runner=runner,
        )
    assert not any(command[:2] == ["docker", "pull"] for command in runner.commands)

    fixture = _portable_handoff_fixture(tmp_path / "missing")
    runner = HydrationRunner(fixture["role_paths"])
    _install_hydration_test_doubles(monkeypatch, fixture, runner)
    monkeypatch.setattr(
        provider,
        "_verify_image_manifest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            freeze.TrustedFreezeError("OCI object is missing")
        ),
    )
    with pytest.raises(freeze.TrustedFreezeError, match="missing"):
        provider.hydrate_handoff(
            fixture["handoff_path"],
            fixture["observation_path"],
            fixture["freeze_evidence_path"],
            tmp_path / "missing" / "fresh-reviewer",
            tmp_path / "missing" / "local-view.json",
            runner=runner,
        )
    assert not any(command[:2] == ["docker", "pull"] for command in runner.commands)

    fixture = _portable_handoff_fixture(tmp_path / "substitution")
    runner = HydrationRunner(fixture["role_paths"], substitute_role="review_bundle")
    _install_hydration_test_doubles(monkeypatch, fixture, runner)
    root = tmp_path / "substitution" / "fresh-reviewer"
    with pytest.raises(freeze.TrustedFreezeError, match="role bytes"):
        provider.hydrate_handoff(
            fixture["handoff_path"],
            fixture["observation_path"],
            fixture["freeze_evidence_path"],
            root,
            tmp_path / "substitution" / "local-view.json",
            runner=runner,
        )
    assert not root.exists()


@pytest.mark.parametrize("writable_target", ["backing", "view"])
def test_portable_hydration_rejects_writable_backing_or_exposed_view(
    writable_target: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _portable_handoff_fixture(tmp_path)
    runner = HydrationRunner(fixture["role_paths"])

    def reject_writable(path: Path, backing_path: Path | None) -> None:
        if (writable_target == "backing" and backing_path is None) or (
            writable_target == "view" and backing_path is not None
        ):
            raise freeze.TrustedFreezeError("authority role is not on a read-only filesystem")

    _install_hydration_test_doubles(
        monkeypatch,
        fixture,
        runner,
        protection_check=reject_writable,
    )
    root = tmp_path / "fresh-reviewer"
    with pytest.raises(freeze.TrustedFreezeError, match="read-only filesystem"):
        provider.hydrate_handoff(
            fixture["handoff_path"],
            fixture["observation_path"],
            fixture["freeze_evidence_path"],
            root,
            tmp_path / "reviewer-local-view.json",
            runner=runner,
        )
    assert not root.exists()


def test_portable_run_identity_rejects_stale_or_cross_repository_producer() -> None:
    observation = _portable_observation()
    freeze_document = evidence()
    assert handoff_module.portable_run_identity(observation, freeze_document) == run_identity()

    stale_run = json.loads(json.dumps(observation))
    stale_run["observation"]["run_id"] = "73125"
    with pytest.raises(freeze.TrustedFreezeError, match="different runs"):
        handoff_module.portable_run_identity(stale_run, freeze_document)

    foreign_repository = json.loads(json.dumps(observation))
    foreign_repository["producer"]["repository_id"] = "1315875003"
    with pytest.raises(freeze.TrustedFreezeError, match="untrusted"):
        handoff_module.portable_run_identity(foreign_repository, freeze_document)


def test_portable_hydration_rejects_stale_pr_target_and_altered_freeze_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _portable_handoff_fixture(tmp_path / "stale-target")
    fixture["handoff"]["target"]["pull_request"]["head_ref_oid"] = "1" * 40
    fixture["handoff_path"].write_text(
        json.dumps(fixture["handoff"], indent=2, sort_keys=True) + "\n"
    )
    runner = HydrationRunner(fixture["role_paths"])
    _install_hydration_test_doubles(monkeypatch, fixture, runner)
    with pytest.raises(actions.TrustedObservationError, match="head commit"):
        provider.hydrate_handoff(
            fixture["handoff_path"],
            fixture["observation_path"],
            fixture["freeze_evidence_path"],
            tmp_path / "stale-target" / "fresh-reviewer",
            tmp_path / "stale-target" / "local-view.json",
            runner=runner,
        )
    assert not any(command[:2] == ["docker", "pull"] for command in runner.commands)

    fixture = _portable_handoff_fixture(tmp_path / "altered-evidence")
    altered = json.loads(fixture["freeze_evidence_path"].read_bytes())
    next(role for role in altered["roles"] if role["role"] == "review_bundle")["identity"][
        "manifest_sha256"
    ] = "f" * 64
    fixture["freeze_evidence_path"].write_text(json.dumps(altered))
    runner = HydrationRunner(fixture["role_paths"])
    _install_hydration_test_doubles(monkeypatch, fixture, runner)
    with pytest.raises(freeze.TrustedFreezeError, match="handoff digest"):
        provider.hydrate_handoff(
            fixture["handoff_path"],
            fixture["observation_path"],
            fixture["freeze_evidence_path"],
            tmp_path / "altered-evidence" / "fresh-reviewer",
            tmp_path / "altered-evidence" / "local-view.json",
            runner=runner,
        )
    assert not any(command[:2] == ["docker", "pull"] for command in runner.commands)


def test_reviewer_local_view_is_bound_to_exact_handoff_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _portable_handoff_fixture(tmp_path)
    runner = HydrationRunner(fixture["role_paths"])
    _install_hydration_test_doubles(monkeypatch, fixture, runner)
    local_view_path = tmp_path / "reviewer-local-view.json"
    provider.hydrate_handoff(
        fixture["handoff_path"],
        fixture["observation_path"],
        fixture["freeze_evidence_path"],
        tmp_path / "fresh-reviewer",
        local_view_path,
        runner=runner,
    )
    local_view = json.loads(local_view_path.read_bytes())
    altered_handoff = json.loads(fixture["handoff_path"].read_bytes())
    altered_handoff["target"]["pull_request"]["head_ref_oid"] = "1" * 40
    altered_digest = hashlib.sha256(
        json.dumps(altered_handoff, sort_keys=True).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="bound to different handoff bytes"):
        handoff_module._validate_local_view(local_view, altered_handoff, altered_digest)

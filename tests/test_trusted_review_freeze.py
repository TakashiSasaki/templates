from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import trusted_review_freeze as freeze
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


def run_identity() -> ActionsRunIdentity:
    return ActionsRunIdentity(
        repository="TakashiSasaki/templates",
        repository_id=REPO_ID,
        run_id="73124",
        run_attempt=2,
        event="workflow_dispatch",
        ref="refs/heads/site",
        workflow_ref=(
            "TakashiSasaki/templates/.github/workflows/trusted-review-bootstrap.yml@refs/heads/site"
        ),
        workflow_sha=WORKFLOW_SHA,
        source_sha=SOURCE_SHA,
    )


def evidence() -> dict[str, Any]:
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
            "run_attempt": 2,
            "event": "workflow_dispatch",
        },
        "target": {
            "repository_id": REPO_ID,
            "repository_name": "TakashiSasaki/templates",
            "pull_request_id": "81001",
            "pull_request_node_id": "PR_kwDOExample",
            "pull_request_number": 97,
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


def handoff() -> dict[str, Any]:
    return {
        "freeze_evidence": {},
        "target": {
            "repository": {"id": REPO_ID, "name_with_owner": "TakashiSasaki/templates"},
            "pull_request": {
                "id": "81001",
                "node_id": "PR_kwDOExample",
                "number": 97,
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


def verified_attestation(subject_sha256: str) -> dict[str, Any]:
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
        "runInvocationURI": (
            "https://github.com/TakashiSasaki/templates/actions/runs/73124/attempts/2"
        ),
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


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["attestation"].update(repository_id="999999"),
        lambda value: value["object"].update(media_type="application/vnd.oci.image.index.v1+json"),
        lambda value: value["roles"].append(value["roles"][0]),
        lambda value: value["roles"][1].update(path="roles/runtime_image"),
        lambda value: value["post_freeze_verification"].update(after_use="FAIL"),
    ],
)
def test_schema_rejects_mismatched_target_or_freeze_identity(mutate: Any) -> None:
    document = evidence()
    mutate(document)
    with pytest.raises(freeze.TrustedFreezeError):
        freeze.validate_freeze_evidence(document)


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
    data["freeze_evidence"] = {"sha256": verifier.sha256}

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
    data["freeze_evidence"] = {"sha256": verifier.sha256}
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
    data["freeze_evidence"] = {"sha256": verifier.sha256}
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
    data["freeze_evidence"] = {"sha256": verifier.sha256}
    with pytest.raises(freeze.TrustedFreezeError, match="subject digest"):
        verifier.verify_document_digest(data)


def test_freeze_evidence_requires_its_own_attestation(tmp_path: Path) -> None:
    path = write_evidence(tmp_path, evidence())
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        path,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(bad_file_subject=True),
    )
    data = handoff()
    data["freeze_evidence"] = {"sha256": verifier.sha256}
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
    evidence_path = write_evidence(tmp_path, doc)
    verifier = freeze.GitHubActionsOciFreezeVerifier(
        evidence_path,
        token="test-token",
        run_identity=run_identity(),
        runner=Runner(),
    )
    handoff_data["freeze_evidence"] = {"sha256": verifier.sha256}
    monkeypatch.setattr(freeze, "require_protected_view", lambda *_args, **_kwargs: None)
    verifier.verify_document_digest(handoff_data)
    for _role, section in freeze.ROLE_TO_SECTION.items():
        verifier.verify(section, handoff_data[section])

    (root / "roles/review_bundle/authority.txt").write_text("mutated")
    with pytest.raises(freeze.TrustedFreezeError, match="inventory changed"):
        verifier.verify_post_use(handoff_data)

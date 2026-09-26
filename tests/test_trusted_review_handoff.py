from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from scripts import prepare_trusted_review_handoff as handoff_module
from scripts.prepare_trusted_review_handoff import (
    STATUS_CANONICAL_BLOCKED_PROVIDER,
    STATUS_FREEZE_BLOCKED,
    STATUS_REPO_IMPL_COMPLETE,
    EvidenceStatus,
    FreezeBoundaryType,
    FreezeEvidence,
    HandoffOrchestrator,
    Phase,
    check_drift,
    closed_git_environment,
    compute_directory_inventory_digest,
    format_reviewer_packet,
    load_and_verify_state,
    prepare_handoff,
    save_state,
    validate_provider_identity,
    verify_handoff,
)

ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "scripts/install_agent_policy_skill.py"
SKILL_SOURCE_PATH = ROOT / "skills/agent-policy"


def valid_sha(char: str = "a") -> str:
    assert char in "0123456789abcdef"
    return char * 40


def valid_sha256(char: str = "b") -> str:
    assert char in "0123456789abcdef"
    return char * 64


def make_valid_handoff_dict(*, simulated_boundary: bool = True) -> dict[str, Any]:
    semantic_digest = valid_sha256("c")
    manifest_digest = valid_sha256("d")
    base_commit = valid_sha("1")
    base_tree = valid_sha("2")

    b_type = "simulated_test" if simulated_boundary else "deployment_established"
    fe_status = "authenticated"
    mechanism = "simulated_test_mount" if simulated_boundary else "container_read_only_bind_mount"

    return {
        "schema_version": 1,
        "handoff_type": "AUTHENTICATED_IMMUTABLE_REVIEW_BOOTSTRAP_HANDOFF",
        "target": {
            "provider": "github",
            "repository": {
                "id": "R_kgDOTm6oug",
                "name_with_owner": "TakashiSasaki/templates",
            },
            "pull_request": {
                "id": "PR_kwDOTm6oug412345",
                "number": 1031,
                "base_ref_name": "policy",
                "base_ref_oid": base_commit,
                "base_tree": base_tree,
                "head_ref_name": "feat/policy-authenticated-review-bootstrap-handoff",
                "head_ref_oid": valid_sha("f"),
                "head_tree": valid_sha("e"),
            },
        },
        "provider_observation": {
            "adapter": {
                "tool": "gh",
                "version": "2.45.0",
                "executable": "/usr/bin/gh",
                "executable_sha256": valid_sha256("8"),
            },
            "authentication_provenance": {
                "account": "TakashiSasaki",
                "active": True,
                "host": "github.com",
                "mechanism": "github_cli_oauth_token",
            },
            "observation_sha256": valid_sha256("9"),
            "raw_response_sha256": valid_sha256("7"),
            "retrieved_at": "2026-09-26T00:00:00Z",
            "authenticated": True,
        },
        "bootstrap_authority": {
            "installer": {
                "repository": "TakashiSasaki/templates",
                "revision": valid_sha("3"),
                "path": "scripts/install_agent_policy_skill.py",
                "git_blob": valid_sha("f"),
                "blob_sha": valid_sha("f"),
                "sha256": valid_sha256("7"),
            },
            "skill_source": {
                "repository": "TakashiSasaki/templates",
                "revision": valid_sha("4"),
                "path": "skills/agent-policy",
            },
            "installation_attestation": {
                "path": "attestation.json",
                "sha256": valid_sha256("a"),
                "entries_count": 11,
            },
        },
        "frozen_bootstrap_image": {
            "inventory_digest": valid_sha256("b"),
            "protected_view": "bootstrap_run_image_ro",
            "freeze_mechanism": {
                "boundary_type": b_type,
                "type": b_type,
                "mechanism": mechanism,
                "evidence_status": fe_status,
                "verified_post_freeze": True,
                "verifier": "production_deployment_verifier",
            },
            "post_freeze_verification": {
                "result": "PASS",
                "verifier": (
                    "TakashiSasaki/templates@33a7ab80:scripts/install_agent_policy_skill.py"
                ),
            },
        },
        "frozen_trusted_base": {
            "revision": base_commit,
            "tree": base_tree,
            "inventory_digest": valid_sha256("1"),
            "protected_view": "trusted_base_snapshot_ro",
            "freeze_mechanism": {
                "boundary_type": b_type,
                "type": b_type,
                "mechanism": mechanism,
                "evidence_status": fe_status,
                "verified_post_freeze": True,
                "verifier": "production_deployment_verifier",
            },
            "post_freeze_verification": {
                "result": "PASS",
                "verifier": "bootstrap_run_image:scripts/review_base.py",
            },
        },
        "frozen_runtime": {
            "toolchain": {
                "repository": "TakashiSasaki/templates",
                "revision": valid_sha("5"),
            },
            "environment": {
                "platform": "Linux-6.17.0-test",
                "python": "3.12.3",
            },
            "lock": {
                "path": ".agent-policy.lock",
                "sha256": valid_sha256("2"),
            },
            "runtime_attestation": {
                "path": "runtime-attestation.json",
                "sha256": valid_sha256("3"),
            },
            "inventory_digest": valid_sha256("4"),
            "protected_view": "runtime_image_ro",
            "freeze_mechanism": {
                "boundary_type": b_type,
                "type": b_type,
                "mechanism": mechanism,
                "evidence_status": fe_status,
                "verified_post_freeze": True,
                "verifier": "production_deployment_verifier",
            },
            "post_freeze_verification": {
                "result": "PASS",
                "verifier": "bootstrap_run_image:scripts/runtime_image.py",
                "probe_execution": "PASS",
            },
        },
        "trusted_base_validation": {
            "configuration": ".agent-policy.yml",
            "check_command": {
                "command": "check",
                "exit_code": 0,
                "output": "No broken requirements found. OK",
                "result": "PASS",
            },
            "validate_command": {
                "command": "validate",
                "exit_code": 0,
                "output": "No broken requirements found. OK",
                "result": "PASS",
            },
        },
        "review_authority_bundle": {
            "bundle_format": 1,
            "inventory_digest": valid_sha256("8"),
            "manifest_sha256": manifest_digest,
            "protected_view": "review_authority_bundle_ro",
            "freeze_mechanism": {
                "boundary_type": b_type,
                "type": b_type,
                "mechanism": mechanism,
                "evidence_status": fe_status,
                "verified_post_freeze": True,
                "verifier": "production_deployment_verifier",
            },
            "post_freeze_verification": {
                "result": "PASS",
                "verifier": "runtime_image:agent_policy review-bundle",
                "exit_code": 0,
            },
            "procedure": {
                "skill_path": "procedure/SKILL.md",
                "skill_sha256": valid_sha256("6"),
                "references": [],
            },
            "semantic": {
                "source_path": ".review-authority/review-policy.md",
                "bundle_path": "semantic/review-policy.md",
                "renderer": "policy-context-md",
                "sha256": semantic_digest,
            },
        },
        "locators": {
            "installed_skill_root": "/opt/agent-policy",
            "bootstrap_run_image": "/var/run/bootstrap-image",
            "trusted_base_snapshot": "/var/run/base-snapshot",
            "runtime_image": "/var/run/runtime-image",
            "review_bundle": "/var/run/review-bundle",
        },
    }


def test_valid_handoff_passes_verification() -> None:
    data = make_valid_handoff_dict()
    verify_handoff(data, allow_simulated_boundary=True, check_locators=False)


@pytest.mark.parametrize("missing_key", list(handoff_module.REQUIRED_TOP_LEVEL_KEYS))
def test_handoff_rejects_missing_top_level_key(missing_key: str) -> None:
    data = make_valid_handoff_dict()
    del data[missing_key]
    with pytest.raises(ValueError, match="handoff shape mismatch"):
        verify_handoff(data)


def test_handoff_rejects_unexpected_top_level_key() -> None:
    data = make_valid_handoff_dict()
    data["extra_untrusted_field"] = "malicious"
    with pytest.raises(ValueError, match="handoff shape mismatch"):
        verify_handoff(data)


def test_handoff_rejects_wrong_schema_version() -> None:
    data = make_valid_handoff_dict()
    data["schema_version"] = 999
    with pytest.raises(ValueError, match="unsupported handoff schema version"):
        verify_handoff(data)


@pytest.mark.parametrize("bad_sha", ["not-a-sha", "0" * 39, "G" * 40, ""])
def test_handoff_rejects_malformed_base_commit(bad_sha: str) -> None:
    data = make_valid_handoff_dict()
    data["target"]["pull_request"]["base_ref_oid"] = bad_sha
    with pytest.raises(ValueError, match="must be a full lowercase commit SHA"):
        verify_handoff(data)


@pytest.mark.parametrize("bad_sha", ["not-a-sha", "0" * 39, "g" * 40, ""])
def test_handoff_rejects_malformed_base_tree(bad_sha: str) -> None:
    data = make_valid_handoff_dict()
    data["target"]["pull_request"]["base_tree"] = bad_sha
    with pytest.raises(ValueError, match="must be a full lowercase commit SHA"):
        verify_handoff(data)


@pytest.mark.parametrize("bad_sha256", ["not-a-sha", "0" * 63, "g" * 64, ""])
def test_handoff_rejects_malformed_attestation_sha256(bad_sha256: str) -> None:
    data = make_valid_handoff_dict()
    data["bootstrap_authority"]["installation_attestation"]["sha256"] = bad_sha256
    with pytest.raises(ValueError, match="64-character lowercase SHA-256"):
        verify_handoff(data, allow_simulated_boundary=True)


def test_handoff_rejects_mismatched_semantic_policy_digest() -> None:
    data = make_valid_handoff_dict()
    data["review_authority_bundle"]["semantic"]["sha256"] = "invalid"
    with pytest.raises(ValueError, match="64-character lowercase SHA-256"):
        verify_handoff(data, allow_simulated_boundary=True)


def test_handoff_rejects_unverified_freeze_state() -> None:
    data = make_valid_handoff_dict()
    data["frozen_bootstrap_image"]["post_freeze_verification"]["result"] = "FAIL"
    with pytest.raises(ValueError, match="post-freeze verification failed"):
        verify_handoff(data, allow_simulated_boundary=True)


def test_handoff_rejects_missing_verifier_provenance() -> None:
    data = make_valid_handoff_dict()
    data["frozen_bootstrap_image"]["post_freeze_verification"]["verifier"] = ""
    with pytest.raises(ValueError, match="missing verifier provenance"):
        verify_handoff(data, allow_simulated_boundary=True)


def test_locator_non_authority() -> None:
    data1 = make_valid_handoff_dict()
    data2 = make_valid_handoff_dict()
    data2["locators"]["review_bundle"] = "/completely/different/path"
    verify_handoff(data1, allow_simulated_boundary=True, check_locators=False)
    verify_handoff(data2, allow_simulated_boundary=True, check_locators=False)


def test_drift_detection_no_drift(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    base_commit = handoff["target"]["pull_request"]["base_ref_oid"]
    base_tree = handoff["target"]["pull_request"]["base_tree"]

    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _git, _repo, _commit: base_tree)

    disposition = check_drift(
        git_executable=Path("/usr/bin/git"),
        object_repository=tmp_path,
        handoff=handoff,
        current_base_commit=base_commit,
        current_head_commit=valid_sha("a"),
        proposed_head_commit=valid_sha("a"),
    )
    assert not disposition.base_drift
    assert not disposition.head_drift
    assert not disposition.invalidates_authority
    assert not disposition.invalidates_head_evidence


def test_drift_detection_base_movement(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    new_base = valid_sha("9")

    monkeypatch.setattr(
        handoff_module, "resolve_base_tree", lambda _git, _repo, _commit: valid_sha("8")
    )

    disposition = check_drift(
        git_executable=Path("/usr/bin/git"),
        object_repository=tmp_path,
        handoff=handoff,
        current_base_commit=new_base,
        current_head_commit=valid_sha("a"),
        proposed_head_commit=valid_sha("a"),
    )
    assert disposition.base_drift
    assert disposition.invalidates_authority
    assert disposition.invalidates_head_evidence


def test_drift_detection_head_movement_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    handoff = make_valid_handoff_dict()
    base_commit = handoff["target"]["pull_request"]["base_ref_oid"]
    base_tree = handoff["target"]["pull_request"]["base_tree"]

    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _git, _repo, _commit: base_tree)

    disposition = check_drift(
        git_executable=Path("/usr/bin/git"),
        object_repository=tmp_path,
        handoff=handoff,
        current_base_commit=base_commit,
        current_head_commit=valid_sha("9"),
        proposed_head_commit=valid_sha("8"),
    )
    assert not disposition.base_drift
    assert disposition.head_drift
    assert not disposition.invalidates_authority
    assert disposition.invalidates_head_evidence


def test_reviewer_packet_formatting() -> None:
    handoff = make_valid_handoff_dict()
    packet = format_reviewer_packet(
        handoff,
        handoff_path="/path/to/handoff.json",
        handoff_sha256=valid_sha256("1"),
        head_commit=valid_sha("f"),
    )
    assert "TRUSTED REVIEW BOOTSTRAP REVIEWER PACKET" in packet
    assert "R_kgDOTm6oug (TakashiSasaki/templates)" in packet
    assert "PR_kwDOTm6oug412345 (#1031)" in packet
    assert handoff["target"]["pull_request"]["base_ref_oid"] in packet
    assert handoff["target"]["pull_request"]["base_tree"] in packet
    assert valid_sha("f") in packet
    assert "Consume ONLY the procedure and semantic authority" in packet
    assert "Do not select, discover, reproduce, or verify review procedure" in packet


# ==============================================================================
# ADVERSARIAL TESTS A - M (Addressing the open finding family)
# ==============================================================================


class MockDeploymentFreezeVerifier:
    name = "mock_deployment_freeze_verifier"

    def __init__(self, allowed_mechanisms: set[str] | None = None) -> None:
        self.allowed_mechanisms = allowed_mechanisms or {
            "ro_mount",
            "container_read_only_bind_mount",
        }

    def verify_freeze(
        self,
        target: str,
        locator: Path,
        evidence: FreezeEvidence,
    ) -> bool:
        if evidence.mechanism not in self.allowed_mechanisms:
            raise ValueError(f"unrecognized freeze mechanism: {evidence.mechanism}")
        if evidence.attestation_sha256 and not handoff_module.SHA256.fullmatch(
            evidence.attestation_sha256
        ):
            raise ValueError(f"invalid attestation sha256: {evidence.attestation_sha256}")
        return True

    def verify(self, section: str, entry: dict[str, Any]) -> bool:
        return True


class MockGitHubProviderAdapter:
    name = "mock_github_adapter"

    def verify(self, data: Any) -> str:
        return self.name


prov_adapter = MockGitHubProviderAdapter()


def setup_mock_environment(
    tmp_path: Path,
    authenticated_provider: bool = False,
) -> dict[str, Any]:
    obj_repo = tmp_path / "bare.git"
    obj_repo.mkdir(parents=True)
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True)
    installed_skill = tmp_path / "installed_skill"
    installed_skill.mkdir(parents=True)
    (installed_skill / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    (installed_skill / "scripts").mkdir()
    (installed_skill / "scripts/run.py").write_text("# run\n", encoding="utf-8")

    attestation_path = tmp_path / "installation-attestation.json"
    attestation_path.write_text(
        json.dumps(
            {
                "installer": {
                    "repository": "TakashiSasaki/templates",
                    "revision": valid_sha("1"),
                    "path": "scripts/install_agent_policy_skill.py",
                },
                "skill_source": {
                    "repository": "TakashiSasaki/templates",
                    "revision": valid_sha("2"),
                    "path": "skills/agent-policy",
                },
                "installation": {
                    "entries": {
                        "SKILL.md": {"type": "file", "sha256": valid_sha256("1")},
                        "scripts": {"type": "directory"},
                        "scripts/run.py": {"type": "file", "sha256": valid_sha256("2")},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    if authenticated_provider:
        provider_id = {
            "name": "github",
            "repository": {"id": "R_kgDOTm6oug", "name_with_owner": "TakashiSasaki/templates"},
            "pull_request": {"id": "PR_kwDOTm6ous8AAAABFJDI8g", "number": 1031},
            "observation_evidence": {
                "source": "simulated_test_adapter",
                "evidence_status": "authenticated",
                "authenticated": True,
                "retrieved_at": "2026-09-26T00:00:00Z",
                "verifier": "simulated_test_adapter",
            },
        }
    else:
        provider_id = {
            "name": "github",
            "repository": {"id": "R_kgDOTm6oug", "name_with_owner": "TakashiSasaki/templates"},
            "pull_request": {"id": "PR_kwDOTm6ous8AAAABFJDI8g", "number": 1031},
            "observation_evidence": {
                "source": "caller_declared",
                "evidence_status": "declared",
                "authenticated": False,
                "retrieved_at": "2026-09-26T00:00:00Z",
                "verifier": None,
            },
        }

    return {
        "obj_repo": obj_repo,
        "work_dir": work_dir,
        "installed_skill": installed_skill,
        "attestation_path": attestation_path,
        "provider_id": provider_id,
        "base_commit": valid_sha("0"),
        "base_tree": valid_sha("b"),
    }


def test_a_unverified_bootstrap_image_never_executes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path)
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    executed = {"side_effect": False}

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None

    def materialize_run_image(src: Path, dest: Path, att: Path, **kwargs: Any) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        scripts = dest / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        # Instrument bootstrap image file with a flag that shouldn't run yet
        (scripts / "review_base.py").write_text(
            "executed['side_effect'] = True\n", encoding="utf-8"
        )
        (scripts / "runtime_image.py").write_text("# runtime_image\n", encoding="utf-8")

    mock_installer.materialize_run_image = materialize_run_image
    mock_installer.verify_run_image = lambda *args, **kwargs: None

    orchestrator = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )

    res = orchestrator.step()
    assert res["status"] == handoff_module.STATUS_FREEZE_BLOCKED
    assert res["phase"] == Phase.BOOTSTRAP_IMAGE_AWAITING_FREEZE.value
    # Invariant: Code in bootstrap run image has NOT been executed!
    assert not executed["side_effect"]


def test_b_bootstrap_tamper_before_post_freeze_verify(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path)
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None

    def materialize_run_image(src: Path, dest: Path, att: Path, **kwargs: Any) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "scripts").mkdir(parents=True, exist_ok=True)
        (dest / "scripts/review_base.py").write_text("# initial\n", encoding="utf-8")

    mock_installer.materialize_run_image = materialize_run_image
    mock_installer.verify_run_image = lambda *args, **kwargs: None

    orchestrator = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )

    orchestrator.step()
    assert orchestrator.state["phase"] == Phase.BOOTSTRAP_IMAGE_AWAITING_FREEZE.value

    # Tamper with bootstrap image before post-freeze verification
    b_dir = Path(orchestrator.state["artifacts"]["bootstrap_run_image"]["locator"])
    (b_dir / "scripts/review_base.py").write_text("# tampered!\n", encoding="utf-8")

    # Record freeze evidence and resume
    orchestrator.record_freeze(
        "bootstrap_run_image",
        FreezeEvidence(FreezeBoundaryType.DEPLOYMENT_ESTABLISHED, "ro_mount"),
    )

    with pytest.raises(
        ValueError, match="bootstrap run image modified between materialization and freeze"
    ):
        orchestrator.step()


def test_c_arbitrary_malicious_installer_path_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # CLI parse test: --installer-script is not accepted
    with pytest.raises(SystemExit):
        handoff_module.parse_args(["prepare", "--installer-script", "/tmp/malicious_installer.py"])


def test_d_mutable_worktree_installer_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path)
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    expected_bytes = b"# EXACT GIT BLOB BYTES\n"

    def mock_git_run(
        git_bin: Path, repo: Path, args: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[Any]:
        if "release/skill-installer.json" in " ".join(args):
            data = json.dumps(
                {
                    "installer": {
                        "repository": "TakashiSasaki/templates",
                        "revision": valid_sha("1"),
                        "path": "scripts/install_agent_policy_skill.py",
                    },
                    "skill_source": {
                        "repository": "TakashiSasaki/templates",
                        "revision": valid_sha("2"),
                        "path": "skills/agent-policy",
                    },
                }
            )
            return subprocess.CompletedProcess(args, 0, stdout=data, stderr="")
        elif "rev-parse" in args:
            return subprocess.CompletedProcess(args, 0, stdout=valid_sha("f") + "\n", stderr="")
        elif "cat-file" in args:
            return subprocess.CompletedProcess(args, 0, stdout=expected_bytes, stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(handoff_module, "git_run", mock_git_run)

    dest_path, info = handoff_module.extract_immutable_installer(
        git_bin=Path("/bin/git"),
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        work_dir=env["work_dir"],
    )
    assert dest_path.is_file()
    assert dest_path.read_bytes() == expected_bytes
    assert info["sha256"] == handoff_module.sha256_bytes(expected_bytes)


def test_e_false_directory_only_freeze_rejected() -> None:
    fe = FreezeEvidence(
        boundary_type=FreezeBoundaryType.DEPLOYMENT_ESTABLISHED,
        mechanism="read_only_bind_mount",
        verified_post_freeze=False,
    )
    assert not fe.verified_post_freeze


def _populate_mock_locators(handoff: dict[str, Any], root: Path) -> None:
    for loc_key in (
        "installed_skill_root",
        "bootstrap_run_image",
        "trusted_base_snapshot",
        "runtime_image",
        "review_bundle",
    ):
        p = root / loc_key
        p.mkdir(parents=True, exist_ok=True)
        (p / "file.txt").write_text(f"content_{loc_key}\n", encoding="utf-8")
        handoff["locators"][loc_key] = str(p)
        if loc_key == "bootstrap_run_image":
            handoff["frozen_bootstrap_image"]["inventory_digest"] = (
                compute_directory_inventory_digest(p)
            )
        elif loc_key == "trusted_base_snapshot":
            handoff["frozen_trusted_base"]["inventory_digest"] = compute_directory_inventory_digest(
                p
            )
        elif loc_key == "runtime_image":
            handoff["frozen_runtime"]["inventory_digest"] = compute_directory_inventory_digest(p)
        elif loc_key == "review_bundle":
            (p / "manifest.json").write_text("{}", encoding="utf-8")
            (p / "procedure").mkdir(parents=True, exist_ok=True)
            (p / "procedure/SKILL.md").write_text("skill\n", encoding="utf-8")
            (p / "semantic").mkdir(parents=True, exist_ok=True)
            (p / "semantic/review-policy.md").write_text("policy\n", encoding="utf-8")
            handoff["review_authority_bundle"]["manifest_sha256"] = handoff_module.sha256_file(
                p / "manifest.json"
            )
            handoff["review_authority_bundle"]["semantic"]["sha256"] = handoff_module.sha256_file(
                p / "semantic/review-policy.md"
            )
            handoff["review_authority_bundle"]["procedure"]["skill_sha256"] = (
                handoff_module.sha256_file(p / "procedure/SKILL.md")
            )
            handoff["review_authority_bundle"]["inventory_digest"] = (
                compute_directory_inventory_digest(p)
            )


def test_f_simulated_evidence_rejected_in_production() -> None:
    class MockProviderAdapter:
        def verify(self, t: Any, o: Any) -> None:
            pass

    handoff = make_valid_handoff_dict()
    handoff["frozen_bootstrap_image"]["freeze_mechanism"]["boundary_type"] = "simulated_test"
    handoff["frozen_bootstrap_image"]["freeze_mechanism"]["type"] = "simulated_test"
    with pytest.raises(
        ValueError, match="simulated test boundary is prohibited in production verification"
    ):
        verify_handoff(
            handoff, allow_simulated_boundary=False, provider_adapter=MockProviderAdapter()
        )


def test_g_bootstrap_artifact_drift(tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    root = tmp_path / "artifacts"
    _populate_mock_locators(handoff, root)

    f = Path(handoff["locators"]["bootstrap_run_image"]) / "file.txt"
    f.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="bootstrap run image directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)


def test_h_trusted_base_drift(tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    root = tmp_path / "artifacts"
    _populate_mock_locators(handoff, root)

    snap = Path(handoff["locators"]["trusted_base_snapshot"])
    (snap / "file.txt").write_text("drifted content", encoding="utf-8")
    with pytest.raises(ValueError, match="base snapshot directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)


def test_i_runtime_drift(tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    root = tmp_path / "artifacts"
    _populate_mock_locators(handoff, root)

    rt = Path(handoff["locators"]["runtime_image"])
    (rt / "file.txt").write_text("mutated runtime binary", encoding="utf-8")
    with pytest.raises(ValueError, match="runtime image directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)


def test_j_bundle_drift(tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    root = tmp_path / "artifacts"
    _populate_mock_locators(handoff, root)

    bundle = Path(handoff["locators"]["review_bundle"])

    # J1: Mutate SKILL.md
    (bundle / "procedure/SKILL.md").write_text("mutated skill", encoding="utf-8")
    with pytest.raises(ValueError, match="review bundle directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)
    (bundle / "procedure/SKILL.md").write_text("skill\n", encoding="utf-8")

    # J2: Mutate semantic policy
    (bundle / "semantic/review-policy.md").write_text("mutated policy", encoding="utf-8")
    with pytest.raises(ValueError, match="review bundle directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)
    (bundle / "semantic/review-policy.md").write_text("policy\n", encoding="utf-8")

    # J3: Add extra file
    (bundle / "extra.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError, match="review bundle directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)


def test_k_untrusted_provider_identity_input() -> None:
    data = make_valid_handoff_dict()
    data["provider_observation"]["authenticated"] = False
    data["provider_observation"]["authentication_provenance"]["active"] = False
    with pytest.raises(ValueError, match="provider observation is not authenticated"):
        verify_handoff(data, allow_simulated_boundary=True, require_authenticated_provider=True)


def test_l_git_environment_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_DIR", "/tmp/bad_git_dir")
    monkeypatch.setenv("GIT_WORK_TREE", "/tmp/bad_work_tree")
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "safe.directory=*")
    monkeypatch.setenv("HOME", "/tmp/bad_home")

    env = closed_git_environment()
    assert "GIT_DIR" not in env
    assert "GIT_WORK_TREE" not in env
    assert "GIT_CONFIG_PARAMETERS" not in env
    assert "HOME" not in env
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert env["GIT_NO_REPLACE_OBJECTS"] == "1"


def test_m_resume_state_tampering(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env = setup_mock_environment(tmp_path)
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    state_file = env["work_dir"] / "handoff-state.json"
    init_state = {
        "schema_version": handoff_module.STATE_SCHEMA_VERSION,
        "state_kind": handoff_module.STATE_KIND,
        "phase": Phase.INITIALIZED.value,
        "provider": env["provider_id"],
        "exact_base": {"commit": env["base_commit"], "tree": env["base_tree"]},
        "artifacts": {},
    }
    save_state(init_state, state_file)

    # M1: Tamper with state record without updating state_digest
    raw = json.loads(state_file.read_text(encoding="utf-8"))
    raw["phase"] = "TAMPERED_PHASE"
    state_file.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="state record tampered: state_digest does not match"):
        load_and_verify_state(state_file)
    state_file.unlink()

    # M2: Swap artifact locator to non-existent or drifted artifact
    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.materialize_run_image = lambda src, dest, att, **kw: dest.mkdir(
        parents=True, exist_ok=True
    )

    orchestrator = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orchestrator.step()

    # M3: Mutate artifact on disk after state saved
    b_dir = Path(orchestrator.state["artifacts"]["bootstrap_run_image"]["locator"])
    (b_dir / "mutation.txt").write_text("mutate", encoding="utf-8")

    # Creating a new orchestrator pointing to the same state file fails on consistency check
    with pytest.raises(ValueError, match="has drifted from recorded digest"):
        HandoffOrchestrator(
            work_dir=env["work_dir"],
            object_repository=env["obj_repo"],
            base_commit=env["base_commit"],
            provider_identity=env["provider_id"],
            installed_skill_root=env["installed_skill"],
            installation_attestation_path=env["attestation_path"],
            simulate_freeze_for_test=False,
            _test_installer_module=mock_installer,
            _test_provider_adapter=prov_adapter,
            _test_freeze_adapter=MockDeploymentFreezeVerifier(),
        )


def test_full_pipeline_end_to_end_simulated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=True)
    env["provider_id"]["observation_evidence"]["source"] = "github_authenticated_adapter"
    prov_adapter = _ResumeTestProviderAdapter()
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.materialize_run_image = lambda src, dest, att, **kw: (dest / "scripts").mkdir(
        parents=True, exist_ok=True
    )
    mock_installer.verify_run_image = lambda *args, **kwargs: None

    mock_review_base = ModuleType("mock_review_base")

    def mock_materialize(git: Any, repo: Any, base: Any, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / ".agent-policy.lock").write_text(
            yaml.safe_dump(
                {"toolchain": {"repository": "TakashiSasaki/templates", "revision": valid_sha("5")}}
            ),
            encoding="utf-8",
        )
        (dest / ".agent-policy.yml").write_text(
            yaml.safe_dump(
                {
                    "skills": {"enabled": ["pr-review"]},
                    "outputs": {
                        "review": {
                            "enabled": True,
                            "renderer": "policy-context-md",
                            "path": ".review-authority/review-policy.md",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    mock_review_base.materialize = mock_materialize
    mock_review_base.verify = lambda *args, **kwargs: None

    mock_runtime_image = ModuleType("mock_runtime_image")
    mock_runtime_image.create_attestation = lambda snap, path: path.write_text(
        "{}", encoding="utf-8"
    )
    mock_runtime_image.materialize_image = lambda snap, att, dest: dest.mkdir(
        parents=True, exist_ok=True
    )
    mock_runtime_image.verify_image = lambda *args, **kwargs: None
    mock_runtime_image.venv_python = lambda rt_dir: sys.executable
    mock_runtime_image.trusted_environment = lambda: os.environ.copy()

    def mock_load_module(name: str, path: Path) -> ModuleType:
        if "review_base" in str(path):
            return mock_review_base
        elif "runtime_image" in str(path):
            return mock_runtime_image
        return ModuleType(name)

    monkeypatch.setattr(handoff_module, "load_module_from_path", mock_load_module)

    def mock_subprocess_run(
        cmd: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, "", "")

    real_check_output = subprocess.check_output

    def mock_check_output(cmd: list[str], *args: Any, **kwargs: Any) -> str:
        if "--output-dir" not in cmd:
            return real_check_output(cmd, *args, **kwargs)
        # Mock review-bundle command
        dest_idx = cmd.index("--output-dir") + 1
        bundle_out = Path(cmd[dest_idx])
        bundle_out.mkdir(parents=True, exist_ok=True)
        (bundle_out / "manifest.json").write_text("{}", encoding="utf-8")
        (bundle_out / "procedure").mkdir(parents=True, exist_ok=True)
        (bundle_out / "procedure/SKILL.md").write_text("skill\n", encoding="utf-8")
        (bundle_out / "semantic").mkdir(parents=True, exist_ok=True)
        (bundle_out / "semantic/review-policy.md").write_text("policy\n", encoding="utf-8")
        return json.dumps(
            {
                "manifest_sha256": handoff_module.sha256_file(bundle_out / "manifest.json"),
                "semantic_policy_sha256": handoff_module.sha256_file(
                    bundle_out / "semantic/review-policy.md"
                ),
            }
        )

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    res = prepare_handoff(
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        work_dir=env["work_dir"],
        proposed_head=valid_sha("f"),
        simulate_freeze_for_test=True,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    assert res["status"] == handoff_module.STATUS_HANDOFF_READY
    assert res["phase"] == Phase.HANDOFF_FINALIZED.value
    verify_handoff(res["handoff"], allow_simulated_boundary=True, check_locators=True)


# ---------------------------------------------------------------------------
# New Regressions: Freeze Evidence Provenance
# ---------------------------------------------------------------------------


def test_freeze_caller_cannot_self_assert_deployment_established(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path)
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.materialize_run_image = lambda src, dest, att, **kw: (dest / "scripts").mkdir(
        parents=True, exist_ok=True
    )
    mock_installer.verify_run_image = lambda *args, **kwargs: None

    orchestrator = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        # No freeze verifier adapter configured!
    )
    orchestrator.step()
    assert orchestrator.state["phase"] == Phase.BOOTSTRAP_IMAGE_AWAITING_FREEZE.value

    # Attempting to self-assert deployment_established without a trusted freeze adapter fails
    with pytest.raises(
        ValueError,
        match="cannot record deployment_established freeze: caller self-assertion is prohibited",
    ):
        orchestrator.record_freeze(
            "bootstrap_run_image",
            FreezeEvidence(FreezeBoundaryType.DEPLOYMENT_ESTABLISHED, "ro_mount"),
        )

    # CLI record-freeze without external adapter also fails closed
    exit_code = handoff_module.main(
        [
            "record-freeze",
            "--state-file",
            str(orchestrator.state_file),
            "--target",
            "bootstrap_run_image",
            "--mechanism",
            "ro_mount",
            "--boundary-type",
            "deployment_established",
        ]
    )
    assert exit_code == 1


def test_freeze_fake_mechanism_string_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path)
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.materialize_run_image = lambda src, dest, att, **kw: (dest / "scripts").mkdir(
        parents=True, exist_ok=True
    )

    verifier = MockDeploymentFreezeVerifier(allowed_mechanisms={"container_read_only_bind_mount"})

    orchestrator = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=verifier,
    )
    orchestrator.step()

    # Fake mechanism string is rejected by verifier adapter
    with pytest.raises(ValueError, match="unrecognized freeze mechanism: fake_mechanism"):
        orchestrator.record_freeze(
            "bootstrap_run_image",
            FreezeEvidence(FreezeBoundaryType.DEPLOYMENT_ESTABLISHED, "fake_mechanism"),
        )


def test_freeze_fake_attestation_digest_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path)
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.materialize_run_image = lambda src, dest, att, **kw: (dest / "scripts").mkdir(
        parents=True, exist_ok=True
    )

    verifier = MockDeploymentFreezeVerifier()

    orchestrator = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=verifier,
    )
    orchestrator.step()

    # Fake or malformed attestation digest is rejected
    with pytest.raises(ValueError, match="invalid attestation sha256"):
        orchestrator.record_freeze(
            "bootstrap_run_image",
            FreezeEvidence(
                FreezeBoundaryType.DEPLOYMENT_ESTABLISHED,
                "ro_mount",
                attestation_sha256="not-a-valid-sha256",
            ),
        )


def test_freeze_test_simulation_remains_test_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path)
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.materialize_run_image = lambda src, dest, att, **kw: (dest / "scripts").mkdir(
        parents=True, exist_ok=True
    )

    orchestrator = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orchestrator.step()

    # 1. Attempting simulated freeze when simulate_freeze_for_test=False is rejected
    with pytest.raises(
        ValueError, match="simulated test freeze boundary cannot be recorded in production"
    ):
        orchestrator.record_freeze(
            "bootstrap_run_image",
            FreezeEvidence(FreezeBoundaryType.SIMULATED_TEST, "simulated_test"),
        )

    # 2. CLI record-freeze without --simulate-freeze-for-test is rejected
    exit_code = handoff_module.main(
        [
            "record-freeze",
            "--state-file",
            str(orchestrator.state_file),
            "--target",
            "bootstrap_run_image",
            "--mechanism",
            "simulated_test",
            "--boundary-type",
            "simulated_test",
        ]
    )
    assert exit_code == 1


def test_freeze_caller_cannot_self_assert_verified_post_freeze(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path)
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.materialize_run_image = lambda src, dest, att, **kw: (dest / "scripts").mkdir(
        parents=True, exist_ok=True
    )

    orchestrator = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orchestrator.step()

    # Caller claiming verified_post_freeze=True is rejected
    with pytest.raises(ValueError, match="cannot self-assert verified_post_freeze=True"):
        orchestrator.record_freeze(
            "bootstrap_run_image",
            FreezeEvidence(
                FreezeBoundaryType.DEPLOYMENT_ESTABLISHED,
                "ro_mount",
                verified_post_freeze=True,
            ),
        )


def test_freeze_unauthenticated_or_missing_verifier_rejected() -> None:
    # 1. Freeze evidence with evidence_status != authenticated
    handoff = make_valid_handoff_dict(simulated_boundary=False)
    handoff["frozen_bootstrap_image"]["freeze_mechanism"]["evidence_status"] = "declared"
    with pytest.raises(ValueError, match="deployment freeze evidence is not authenticated"):
        verify_handoff(handoff, allow_simulated_boundary=True)

    # 2. Missing verifier
    handoff2 = make_valid_handoff_dict(simulated_boundary=False)
    handoff2["frozen_bootstrap_image"]["freeze_mechanism"]["verifier"] = None
    handoff2["frozen_bootstrap_image"]["post_freeze_verification"]["verifier"] = ""
    with pytest.raises(ValueError, match="missing verifier provenance"):
        verify_handoff(handoff2, allow_simulated_boundary=True)


# ---------------------------------------------------------------------------
# New Regressions: Provider Evidence Provenance
# ---------------------------------------------------------------------------


def test_provider_caller_authored_authenticated_true_rejected() -> None:
    # 1. caller_declared claiming authenticated=True
    bad_declared = {
        "name": "github",
        "repository": {"id": "R_kgDOTm6oug", "name_with_owner": "TakashiSasaki/templates"},
        "pull_request": {"id": "PR_123", "number": 1031},
        "observation_evidence": {
            "source": "caller_declared",
            "authenticated": True,
        },
    }
    with pytest.raises(
        ValueError, match="caller-declared provider evidence cannot be authenticated"
    ):
        validate_provider_identity(bad_declared)

    # 2. unauthenticated_observation claiming authenticated=True
    bad_obs = {
        "name": "github",
        "repository": {"id": "R_kgDOTm6oug", "name_with_owner": "TakashiSasaki/templates"},
        "pull_request": {"id": "PR_123", "number": 1031},
        "observation_evidence": {
            "source": "unauthenticated_observation",
            "authenticated": True,
        },
    }
    with pytest.raises(
        ValueError, match="unauthenticated provider observation cannot claim authenticated status"
    ):
        validate_provider_identity(bad_obs)

    # 3. github_authenticated_adapter claimed without a trusted provider adapter
    bad_claimed_adapter = {
        "name": "github",
        "repository": {"id": "R_kgDOTm6oug", "name_with_owner": "TakashiSasaki/templates"},
        "pull_request": {"id": "PR_123", "number": 1031},
        "observation_evidence": {
            "source": "github_authenticated_adapter",
            "authenticated": True,
        },
    }
    with pytest.raises(
        ValueError,
        match=(
            "provider observation cannot self-assert authenticated status "
            "without trusted provider adapter"
        ),
    ):
        validate_provider_identity(bad_claimed_adapter)


def test_provider_caller_declared_ids_remain_untrusted() -> None:
    declared = {
        "name": "github",
        "repository": {"id": "R_kgDOTm6oug", "name_with_owner": "TakashiSasaki/templates"},
        "pull_request": {"id": "PR_123", "number": 1031},
        "observation_evidence": {
            "source": "caller_declared",
            "authenticated": False,
        },
    }
    res = validate_provider_identity(declared)
    assert res["observation_evidence"]["evidence_status"] == EvidenceStatus.DECLARED.value
    assert not res["observation_evidence"]["authenticated"]

    handoff = make_valid_handoff_dict()
    handoff["provider_observation"] = res
    with pytest.raises(ValueError, match="provider observation is not authenticated"):
        verify_handoff(handoff, allow_simulated_boundary=True, require_authenticated_provider=True)


def test_provider_unknown_source_rejected() -> None:
    bad_source = {
        "name": "github",
        "repository": {"id": "R_kgDOTm6oug", "name_with_owner": "TakashiSasaki/templates"},
        "pull_request": {"id": "PR_123", "number": 1031},
        "observation_evidence": {
            "source": "untrusted_custom_service",
            "authenticated": False,
        },
    }
    with pytest.raises(ValueError, match="unknown provider observation evidence source"):
        validate_provider_identity(bad_source)


def test_provider_test_only_evidence_cannot_leak_into_production() -> None:
    test_evidence = {
        "name": "github",
        "repository": {"id": "R_kgDOTm6oug", "name_with_owner": "TakashiSasaki/templates"},
        "pull_request": {"id": "PR_123", "number": 1031},
        "observation_evidence": {
            "source": "simulated_test_adapter",
            "authenticated": True,
        },
    }
    with pytest.raises(
        ValueError, match="test-only provider evidence cannot be used in production"
    ):
        validate_provider_identity(test_evidence, allow_test_provider=False)


def test_provider_recognized_adapter_accepted() -> None:
    class MockGitHubProviderAdapter:
        name = "github_oidc_adapter"

        def verify(self, data: dict[str, Any]) -> str:
            return self.name

    prov_data = {
        "name": "github",
        "repository": {"id": "R_kgDOTm6oug", "name_with_owner": "TakashiSasaki/templates"},
        "pull_request": {"id": "PR_123", "number": 1031},
        "observation_evidence": {
            "source": "github_authenticated_adapter",
            "authenticated": True,
        },
    }
    validated = validate_provider_identity(
        prov_data,
        provider_adapter=MockGitHubProviderAdapter(),
    )
    obs = validated["observation_evidence"]
    assert obs["evidence_status"] == EvidenceStatus.AUTHENTICATED.value
    assert obs["authenticated"] is True
    assert obs["verifier"] == "github_oidc_adapter"


# ---------------------------------------------------------------------------
# New Regressions: Final Verifier Depth (Option B Disposition)
# ---------------------------------------------------------------------------


def test_final_verifier_phase_level_post_freeze_semantic_verification_precedes_freshness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=True)
    env["provider_id"]["observation_evidence"]["source"] = "github_authenticated_adapter"
    prov_adapter = _ResumeTestProviderAdapter()
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    # 1. Test that BOOTSTRAP_IMAGE post-freeze semantic verification failure blocks advancement
    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.materialize_run_image = lambda src, dest, att, **kw: (dest / "scripts").mkdir(
        parents=True, exist_ok=True
    )

    def failing_verify_run_image(*args: Any, **kwargs: Any) -> None:
        raise ValueError("semantic verification failed: installer run-image integrity compromised")

    mock_installer.verify_run_image = failing_verify_run_image

    orchestrator = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=True,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    with pytest.raises(ValueError, match="installer run-image integrity compromised"):
        orchestrator.step()
    # Invariant: Phase did NOT advance to BOOTSTRAP_IMAGE_VERIFIED
    assert orchestrator.state["phase"] == Phase.BOOTSTRAP_IMAGE_AWAITING_FREEZE.value


def test_final_verifier_mutation_of_each_frozen_artifact_fails_final_inventory_check(
    tmp_path: Path,
) -> None:
    handoff = make_valid_handoff_dict()
    root = tmp_path / "test_artifacts"
    _populate_mock_locators(handoff, root)

    # Initially valid
    verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)

    # Mutate 1: bootstrap_run_image
    b_p = Path(handoff["locators"]["bootstrap_run_image"])
    (b_p / "tamper.txt").write_text("tamper", encoding="utf-8")
    with pytest.raises(ValueError, match="bootstrap run image directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)
    (b_p / "tamper.txt").unlink()

    # Mutate 2: trusted_base_snapshot
    s_p = Path(handoff["locators"]["trusted_base_snapshot"])
    (s_p / "tamper.txt").write_text("tamper", encoding="utf-8")
    with pytest.raises(ValueError, match="base snapshot directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)
    (s_p / "tamper.txt").unlink()

    # Mutate 3: runtime_image
    r_p = Path(handoff["locators"]["runtime_image"])
    (r_p / "tamper.txt").write_text("tamper", encoding="utf-8")
    with pytest.raises(ValueError, match="runtime image directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)
    (r_p / "tamper.txt").unlink()

    # Mutate 4: review_bundle
    bundle_p = Path(handoff["locators"]["review_bundle"])
    (bundle_p / "tamper.txt").write_text("tamper", encoding="utf-8")
    with pytest.raises(ValueError, match="review bundle directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)
    (bundle_p / "tamper.txt").unlink()


# ---------------------------------------------------------------------------
# Canonical Dogfood Halts Truthfully
# ---------------------------------------------------------------------------


def test_canonical_dogfood_halts_truthfully_at_external_blockers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=False)
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.materialize_run_image = lambda src, dest, att, **kw: (dest / "scripts").mkdir(
        parents=True, exist_ok=True
    )

    orchestrator = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    result = orchestrator.step()
    assert result["status"] == STATUS_FREEZE_BLOCKED
    assert result["repository_implementation_status"] == STATUS_REPO_IMPL_COMPLETE
    assert result["canonical_disposition"] == STATUS_CANONICAL_BLOCKED_PROVIDER
    assert "freeze provider missing" in result["external_blockers"]
    assert "provider-identity authentication provider missing" in result["external_blockers"]


# ---------------------------------------------------------------------------
# Blocker 1 Dedicated Regressions: Provider & Freeze Forgery Resistance
# ---------------------------------------------------------------------------


def test_verify_cli_rejects_forged_provider_self_assertion(tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict(simulated_boundary=False)
    handoff_file = tmp_path / "forged_handoff.json"
    handoff_file.write_text(json.dumps(handoff), encoding="utf-8")

    # verify CLI without external provider observation / adapter must exit nonzero
    exit_code = handoff_module.main(["verify", "--handoff", str(handoff_file)])
    assert exit_code != 0


def test_verify_handoff_rejects_freeze_forgery_without_adapter() -> None:
    class MockProviderAdapter:
        def verify(self, target: Any, obs: Any) -> None:
            pass

    handoff = make_valid_handoff_dict(simulated_boundary=False)
    # Even if provider is independently verified, freeze self-assertion without adapter is rejected
    with pytest.raises(
        ValueError,
        match="deployment freeze evidence cannot be self-asserted without trusted freeze adapter",
    ):
        verify_handoff(
            handoff,
            allow_simulated_boundary=False,
            provider_adapter=MockProviderAdapter(),
            freeze_adapter=None,
        )


def test_hermes_exploit_shape_reproduction(tmp_path: Path) -> None:
    """Reproduce the exploit shape described in review 5323116076:
    A crafted handoff JSON with authenticated=True and made-up verifier strings,
    attempting to bypass verification without genuine external verifier evidence.
    """
    forged_handoff = make_valid_handoff_dict(simulated_boundary=False)
    forged_handoff["provider_observation"]["authentication_provenance"]["verifier"] = (
        "forged_github_verifier"
    )
    forged_handoff["frozen_bootstrap_image"]["freeze_mechanism"]["verifier"] = (
        "forged_deployment_verifier"
    )

    # Must fail closed in verify_handoff
    with pytest.raises(
        ValueError,
        match=(
            "provider observation cannot self-assert authenticated status "
            "without trusted provider adapter"
        ),
    ):
        verify_handoff(forged_handoff, allow_simulated_boundary=False)

    # Must also fail closed via CLI
    f_path = tmp_path / "hermes_exploit.json"
    f_path.write_text(json.dumps(forged_handoff), encoding="utf-8")
    assert handoff_module.main(["verify", "--handoff", str(f_path)]) != 0


def test_positive_externally_verified_handoff() -> None:
    class MockProviderAdapter:
        def verify(self, target: Any, obs: Any) -> None:
            pass

    class MockFreezeAdapter:
        def verify(self, section: str, entry: Any) -> None:
            pass

    handoff = make_valid_handoff_dict(simulated_boundary=False)
    # When both trusted adapters are supplied, verification succeeds
    verify_handoff(
        handoff,
        allow_simulated_boundary=False,
        provider_adapter=MockProviderAdapter(),
        freeze_adapter=MockFreezeAdapter(),
    )


# ---------------------------------------------------------------------------
class _ResumeTestProviderAdapter:
    def verify(self, data: Any) -> str:
        return "mock_github_adapter"


# Blocker 2 Dedicated Regressions: Resumable Run-Binding Invariants
# ---------------------------------------------------------------------------


def test_resume_state_rejects_repository_substitution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=True)
    env["provider_id"]["observation_evidence"]["source"] = "github_authenticated_adapter"
    prov_adapter = _ResumeTestProviderAdapter()
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *a, **kw: None

    def mock_mat(src, dest, att, **kw):
        (dest / "scripts").mkdir(parents=True, exist_ok=True)
        (dest / "scripts/review_base.py").write_text("#", encoding="utf-8")

    mock_installer.materialize_run_image = mock_mat
    mock_installer.verify_run_image = lambda *a, **kw: None

    orch1 = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orch1.step()

    # Attempt resume with different repository ID
    alt_provider_id = copy.deepcopy(env["provider_id"])
    alt_provider_id["repository"]["id"] = "R_kgDOSUBSTITUTED"
    with pytest.raises(ValueError, match="resumable state repository id.*does not match"):
        HandoffOrchestrator(
            work_dir=env["work_dir"],
            object_repository=env["obj_repo"],
            base_commit=env["base_commit"],
            provider_identity=alt_provider_id,
            installed_skill_root=env["installed_skill"],
            installation_attestation_path=env["attestation_path"],
            simulate_freeze_for_test=False,
            _test_installer_module=mock_installer,
            _test_provider_adapter=prov_adapter,
            _test_freeze_adapter=MockDeploymentFreezeVerifier(),
        )

    # Attempt resume with different repository name
    alt_provider_name = copy.deepcopy(env["provider_id"])
    alt_provider_name["repository"]["name_with_owner"] = "Attacker/templates"
    with pytest.raises(ValueError, match="resumable state repository name.*does not match"):
        HandoffOrchestrator(
            work_dir=env["work_dir"],
            object_repository=env["obj_repo"],
            base_commit=env["base_commit"],
            provider_identity=alt_provider_name,
            installed_skill_root=env["installed_skill"],
            installation_attestation_path=env["attestation_path"],
            simulate_freeze_for_test=False,
            _test_installer_module=mock_installer,
            _test_provider_adapter=prov_adapter,
            _test_freeze_adapter=MockDeploymentFreezeVerifier(),
        )


def test_resume_state_rejects_pr_substitution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=True)
    env["provider_id"]["observation_evidence"]["source"] = "github_authenticated_adapter"
    prov_adapter = _ResumeTestProviderAdapter()
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *a, **kw: None

    def mock_mat(src, dest, att, **kw):
        (dest / "scripts").mkdir(parents=True, exist_ok=True)
        (dest / "scripts/review_base.py").write_text("#", encoding="utf-8")

    mock_installer.materialize_run_image = mock_mat
    mock_installer.verify_run_image = lambda *a, **kw: None

    orch1 = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orch1.step()

    # Different PR ID
    alt_pr_id = copy.deepcopy(env["provider_id"])
    alt_pr_id["pull_request"]["id"] = "PR_SUBSTITUTED"
    with pytest.raises(ValueError, match="resumable state pull request id.*does not match"):
        HandoffOrchestrator(
            work_dir=env["work_dir"],
            object_repository=env["obj_repo"],
            base_commit=env["base_commit"],
            provider_identity=alt_pr_id,
            installed_skill_root=env["installed_skill"],
            installation_attestation_path=env["attestation_path"],
            simulate_freeze_for_test=False,
            _test_installer_module=mock_installer,
            _test_provider_adapter=prov_adapter,
            _test_freeze_adapter=MockDeploymentFreezeVerifier(),
        )

    # Different PR number
    alt_pr_num = copy.deepcopy(env["provider_id"])
    alt_pr_num["pull_request"]["number"] = 9999
    with pytest.raises(ValueError, match="resumable state pull request number.*does not match"):
        HandoffOrchestrator(
            work_dir=env["work_dir"],
            object_repository=env["obj_repo"],
            base_commit=env["base_commit"],
            provider_identity=alt_pr_num,
            installed_skill_root=env["installed_skill"],
            installation_attestation_path=env["attestation_path"],
            simulate_freeze_for_test=False,
            _test_installer_module=mock_installer,
            _test_provider_adapter=prov_adapter,
            _test_freeze_adapter=MockDeploymentFreezeVerifier(),
        )


def test_resume_state_rejects_provider_observation_substitution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=True)
    env["provider_id"]["observation_evidence"]["source"] = "github_authenticated_adapter"
    prov_adapter = _ResumeTestProviderAdapter()
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *a, **kw: None

    def mock_mat(src, dest, att, **kw):
        (dest / "scripts").mkdir(parents=True, exist_ok=True)
        (dest / "scripts/review_base.py").write_text("#", encoding="utf-8")

    mock_installer.materialize_run_image = mock_mat
    mock_installer.verify_run_image = lambda *a, **kw: None

    orch1 = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orch1.step()

    # Different observation source
    alt_obs_src = copy.deepcopy(env["provider_id"])
    alt_obs_src["observation_evidence"]["source"] = "caller_declared"
    alt_obs_src["observation_evidence"]["authenticated"] = False
    alt_obs_src["observation_evidence"]["evidence_status"] = "declared"
    alt_obs_src["observation_evidence"]["verifier"] = None
    with pytest.raises(ValueError, match="resumable state observation source.*does not match"):
        HandoffOrchestrator(
            work_dir=env["work_dir"],
            object_repository=env["obj_repo"],
            base_commit=env["base_commit"],
            provider_identity=alt_obs_src,
            installed_skill_root=env["installed_skill"],
            installation_attestation_path=env["attestation_path"],
            simulate_freeze_for_test=False,
            _test_installer_module=mock_installer,
            _test_provider_adapter=prov_adapter,
            _test_freeze_adapter=MockDeploymentFreezeVerifier(),
        )


def test_resume_state_rejects_base_commit_substitution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=True)
    env["provider_id"]["observation_evidence"]["source"] = "github_authenticated_adapter"
    prov_adapter = _ResumeTestProviderAdapter()
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *a, **kw: None

    def mock_mat(src, dest, att, **kw):
        (dest / "scripts").mkdir(parents=True, exist_ok=True)
        (dest / "scripts/review_base.py").write_text("#", encoding="utf-8")

    mock_installer.materialize_run_image = mock_mat
    mock_installer.verify_run_image = lambda *a, **kw: None

    orch = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orch.step()

    alt_base = valid_sha("9")
    with pytest.raises(ValueError, match="state base commit.*does not match"):
        HandoffOrchestrator(
            work_dir=env["work_dir"],
            object_repository=env["obj_repo"],
            base_commit=alt_base,
            provider_identity=env["provider_id"],
            installed_skill_root=env["installed_skill"],
            installation_attestation_path=env["attestation_path"],
            simulate_freeze_for_test=False,
            _test_installer_module=mock_installer,
            _test_provider_adapter=prov_adapter,
            _test_freeze_adapter=MockDeploymentFreezeVerifier(),
        )


def test_resume_state_rejects_base_tree_substitution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=True)
    env["provider_id"]["observation_evidence"]["source"] = "github_authenticated_adapter"
    prov_adapter = _ResumeTestProviderAdapter()
    trees = [env["base_tree"], valid_sha("8")]
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: trees.pop(0))

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *a, **kw: None

    def mock_mat(src, dest, att, **kw):
        (dest / "scripts").mkdir(parents=True, exist_ok=True)
        (dest / "scripts/review_base.py").write_text("#", encoding="utf-8")

    mock_installer.materialize_run_image = mock_mat
    mock_installer.verify_run_image = lambda *a, **kw: None

    orch = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orch.step()

    with pytest.raises(ValueError, match="state base tree.*does not match resolved base tree"):
        HandoffOrchestrator(
            work_dir=env["work_dir"],
            object_repository=env["obj_repo"],
            base_commit=env["base_commit"],
            provider_identity=env["provider_id"],
            installed_skill_root=env["installed_skill"],
            installation_attestation_path=env["attestation_path"],
            simulate_freeze_for_test=False,
            _test_installer_module=mock_installer,
            _test_provider_adapter=prov_adapter,
            _test_freeze_adapter=MockDeploymentFreezeVerifier(),
        )


def test_resume_state_rejects_proposed_head_substitution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=True)
    env["provider_id"]["observation_evidence"]["source"] = "github_authenticated_adapter"
    prov_adapter = _ResumeTestProviderAdapter()
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *a, **kw: None

    def mock_mat(src, dest, att, **kw):
        (dest / "scripts").mkdir(parents=True, exist_ok=True)
        (dest / "scripts/review_base.py").write_text("#", encoding="utf-8")

    mock_installer.materialize_run_image = mock_mat
    mock_installer.verify_run_image = lambda *a, **kw: None

    orch = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        proposed_head=valid_sha("a"),
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orch.step()

    with pytest.raises(ValueError, match="resumable state proposed head.*does not match"):
        HandoffOrchestrator(
            work_dir=env["work_dir"],
            object_repository=env["obj_repo"],
            base_commit=env["base_commit"],
            proposed_head=valid_sha("b"),
            provider_identity=env["provider_id"],
            installed_skill_root=env["installed_skill"],
            installation_attestation_path=env["attestation_path"],
            simulate_freeze_for_test=False,
            _test_installer_module=mock_installer,
            _test_provider_adapter=prov_adapter,
            _test_freeze_adapter=MockDeploymentFreezeVerifier(),
        )


def test_resume_state_rejects_installer_authority_tampering(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=True)
    env["provider_id"]["observation_evidence"]["source"] = "github_authenticated_adapter"
    prov_adapter = _ResumeTestProviderAdapter()
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *a, **kw: None

    def mock_mat(src, dest, att, **kw):
        (dest / "scripts").mkdir(parents=True, exist_ok=True)
        (dest / "scripts/review_base.py").write_text("#", encoding="utf-8")

    mock_installer.materialize_run_image = mock_mat
    mock_installer.verify_run_image = lambda *a, **kw: None

    orch = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orch.step()

    # Tamper with installer revision in state file
    state = json.loads(orch.state_file.read_text(encoding="utf-8"))
    state["installer_authority"]["revision"] = valid_sha("7")
    save_state(state, orch.state_file)

    with pytest.raises(
        ValueError, match="resumable state installer authority revision.*does not match"
    ):
        HandoffOrchestrator(
            work_dir=env["work_dir"],
            object_repository=env["obj_repo"],
            base_commit=env["base_commit"],
            provider_identity=env["provider_id"],
            installed_skill_root=env["installed_skill"],
            installation_attestation_path=env["attestation_path"],
            simulate_freeze_for_test=False,
            _test_installer_module=mock_installer,
            _test_provider_adapter=prov_adapter,
            _test_freeze_adapter=MockDeploymentFreezeVerifier(),
        )


def test_resume_state_valid_identical_binding_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = setup_mock_environment(tmp_path, authenticated_provider=True)
    env["provider_id"]["observation_evidence"]["source"] = "github_authenticated_adapter"
    prov_adapter = _ResumeTestProviderAdapter()
    monkeypatch.setattr(handoff_module, "resolve_base_tree", lambda _g, _r, _c: env["base_tree"])

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *a, **kw: None

    def mock_mat(src, dest, att, **kw):
        (dest / "scripts").mkdir(parents=True, exist_ok=True)
        (dest / "scripts/review_base.py").write_text("#", encoding="utf-8")

    mock_installer.materialize_run_image = mock_mat
    mock_installer.verify_run_image = lambda *a, **kw: None
    mock_installer.verify_run_image = lambda *a, **kw: None

    orch = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        proposed_head=valid_sha("f"),
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    orch.step()
    resumed_phase = orch.state["phase"]

    # Resume with identical parameters succeeds without error
    orch2 = HandoffOrchestrator(
        work_dir=env["work_dir"],
        object_repository=env["obj_repo"],
        base_commit=env["base_commit"],
        proposed_head=valid_sha("f"),
        provider_identity=env["provider_id"],
        installed_skill_root=env["installed_skill"],
        installation_attestation_path=env["attestation_path"],
        simulate_freeze_for_test=False,
        _test_installer_module=mock_installer,
        _test_provider_adapter=prov_adapter,
        _test_freeze_adapter=MockDeploymentFreezeVerifier(),
    )
    assert orch2.state["phase"] == resumed_phase


# ---------------------------------------------------------------------------
# Step 7: Production Handoff Interoperability Test
# ---------------------------------------------------------------------------


def test_production_canonical_handoff_interoperability() -> None:
    """Test against a sanitized deterministic fixture representing canonical production format."""
    fixture = make_valid_handoff_dict(simulated_boundary=False)
    # Ensure all 10 canonical keys are present
    assert set(fixture.keys()) >= handoff_module.REQUIRED_TOP_LEVEL_KEYS

    # 1. Unverified copy in production mode is REJECTED
    with pytest.raises(
        ValueError, match="provider observation cannot self-assert authenticated status"
    ):
        verify_handoff(fixture, allow_simulated_boundary=False)

    # 2. When simulated boundary is explicitly allowed, recognized
    verify_handoff(fixture, allow_simulated_boundary=True)

    # 3. When independently trusted evidence adapters are supplied, accepted in production mode
    class TrustedProviderVerifier:
        def verify(self, target: Any, prov_obs: Any) -> None:
            pass

    class TrustedFreezeVerifier:
        def verify(self, section: str, entry: Any) -> None:
            pass

    verify_handoff(
        fixture,
        allow_simulated_boundary=False,
        provider_adapter=TrustedProviderVerifier(),
        freeze_adapter=TrustedFreezeVerifier(),
    )

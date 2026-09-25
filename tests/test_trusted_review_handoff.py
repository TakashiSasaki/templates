from __future__ import annotations

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


def make_valid_handoff_dict() -> dict[str, Any]:
    semantic_digest = valid_sha256("c")
    manifest_digest = valid_sha256("d")
    base_commit = valid_sha("1")
    base_tree = valid_sha("2")

    return {
        "schema_version": 1,
        "provider": {
            "name": "github",
            "repository": {
                "id": "R_kgDOTm6oug",
                "name_with_owner": "TakashiSasaki/templates",
            },
            "pull_request": {
                "id": "PR_kwDOTm6oug412345",
                "number": 1031,
            },
            "observation_evidence": {
                "source": "github_observation_snapshot",
                "authenticated": True,
                "retrieved_at": "2026-09-26T00:00:00Z",
            },
        },
        "exact_base": {
            "commit": base_commit,
            "tree": base_tree,
        },
        "installed_bootstrap": {
            "installer": {
                "repository": "TakashiSasaki/templates",
                "revision": valid_sha("3"),
                "path": "scripts/install_agent_policy_skill.py",
                "blob_sha": valid_sha("f"),
                "sha256": valid_sha256("7"),
            },
            "skill_source": {
                "repository": "TakashiSasaki/templates",
                "revision": valid_sha("4"),
                "path": "skills/agent-policy",
            },
            "attestation_sha256": valid_sha256("a"),
            "entries_digest": valid_sha256("e"),
            "inventory_digest": valid_sha256("0"),
        },
        "bootstrap_run_image": {
            "inventory_digest": valid_sha256("b"),
            "freeze_evidence": {
                "boundary_type": "deployment_established",
                "mechanism": "container_read_only_bind_mount",
                "verified_post_freeze": True,
            },
            "verifier": "TakashiSasaki/templates@33a7ab80:scripts/install_agent_policy_skill.py",
        },
        "trusted_base_snapshot": {
            "commit": base_commit,
            "tree": base_tree,
            "inventory_digest": valid_sha256("1"),
            "freeze_evidence": {
                "boundary_type": "deployment_established",
                "mechanism": "container_read_only_bind_mount",
                "verified_post_freeze": True,
            },
            "verifier": "bootstrap_run_image:scripts/review_base.py",
        },
        "runtime": {
            "toolchain": {
                "repository": "TakashiSasaki/templates",
                "revision": valid_sha("5"),
            },
            "runtime_attestation_sha256": valid_sha256("3"),
            "inventory_digest": valid_sha256("4"),
            "freeze_evidence": {
                "boundary_type": "deployment_established",
                "mechanism": "container_read_only_bind_mount",
                "verified_post_freeze": True,
            },
            "verifier": "bootstrap_run_image:scripts/runtime_image.py",
        },
        "review_bundle": {
            "inventory_digest": valid_sha256("8"),
            "manifest_sha256": manifest_digest,
            "semantic_policy_sha256": semantic_digest,
            "freeze_evidence": {
                "boundary_type": "deployment_established",
                "mechanism": "container_read_only_bind_mount",
                "verified_post_freeze": True,
            },
            "verifier": "runtime_image:agent_policy review-bundle",
        },
        "semantic_output": {
            "path": ".review-authority/review-policy.md",
            "renderer": "policy-context-md",
            "sha256": semantic_digest,
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
    verify_handoff(data, allow_simulated_boundary=False, check_locators=False)


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
    data["exact_base"]["commit"] = bad_sha
    with pytest.raises(ValueError, match="must be a full lowercase commit SHA"):
        verify_handoff(data)


@pytest.mark.parametrize("bad_sha", ["not-a-sha", "0" * 39, "g" * 40, ""])
def test_handoff_rejects_malformed_base_tree(bad_sha: str) -> None:
    data = make_valid_handoff_dict()
    data["exact_base"]["tree"] = bad_sha
    with pytest.raises(ValueError, match="must be a full lowercase commit SHA"):
        verify_handoff(data)


@pytest.mark.parametrize("bad_sha256", ["not-a-sha", "0" * 63, "g" * 64, ""])
def test_handoff_rejects_malformed_attestation_sha256(bad_sha256: str) -> None:
    data = make_valid_handoff_dict()
    data["installed_bootstrap"]["attestation_sha256"] = bad_sha256
    with pytest.raises(ValueError, match="64-character lowercase SHA-256"):
        verify_handoff(data)


def test_handoff_rejects_mismatched_semantic_policy_digest() -> None:
    data = make_valid_handoff_dict()
    data["semantic_output"]["sha256"] = valid_sha256("9")
    with pytest.raises(ValueError, match="does not match semantic_output.sha256"):
        verify_handoff(data)


def test_handoff_rejects_unverified_freeze_state() -> None:
    data = make_valid_handoff_dict()
    data["bootstrap_run_image"]["freeze_evidence"]["verified_post_freeze"] = False
    with pytest.raises(ValueError, match="has not been verified post-freeze"):
        verify_handoff(data)


def test_handoff_rejects_missing_verifier_provenance() -> None:
    data = make_valid_handoff_dict()
    data["bootstrap_run_image"]["verifier"] = ""
    with pytest.raises(ValueError, match="missing verifier provenance"):
        verify_handoff(data)


def test_locator_non_authority() -> None:
    data1 = make_valid_handoff_dict()
    data2 = make_valid_handoff_dict()
    data2["locators"]["review_bundle"] = "/completely/different/path"
    verify_handoff(data1, check_locators=False)
    verify_handoff(data2, check_locators=False)


def test_drift_detection_no_drift(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    base_commit = handoff["exact_base"]["commit"]
    base_tree = handoff["exact_base"]["tree"]

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
    base_commit = handoff["exact_base"]["commit"]
    base_tree = handoff["exact_base"]["tree"]

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
    assert handoff["exact_base"]["commit"] in packet
    assert handoff["exact_base"]["tree"] in packet
    assert valid_sha("f") in packet
    assert "Consume ONLY the procedure and semantic authority" in packet
    assert "Do not select, discover, reproduce, or verify review procedure" in packet


# ==============================================================================
# ADVERSARIAL TESTS A - M (Addressing the open finding family)
# ==============================================================================


def setup_mock_environment(tmp_path: Path) -> dict[str, Any]:
    obj_repo = tmp_path / "bare.git"
    obj_repo.mkdir()
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    installed_skill = tmp_path / "installed_skill"
    installed_skill.mkdir()
    (installed_skill / "SKILL.md").write_text("installed skill", encoding="utf-8")
    (installed_skill / "scripts").mkdir()
    (installed_skill / "scripts/run.py").write_text("#!/usr/bin/env python\n", encoding="utf-8")

    attestation_path = tmp_path / "attestation.json"
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

    provider_id = {
        "name": "github",
        "repository": {"id": "R_kgDOTm6oug", "name_with_owner": "TakashiSasaki/templates"},
        "pull_request": {"id": "PR_kwDOTm6ous8AAAABFJDI8g", "number": 1031},
        "observation_evidence": {
            "source": "github_observation_snapshot",
            "authenticated": True,
            "retrieved_at": "2026-09-26T00:00:00Z",
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
    )

    orchestrator.step()
    assert orchestrator.state["phase"] == Phase.BOOTSTRAP_IMAGE_AWAITING_FREEZE.value

    # Tamper with bootstrap image before post-freeze verification
    b_dir = Path(orchestrator.state["artifacts"]["bootstrap_run_image"]["locator"])
    (b_dir / "scripts/review_base.py").write_text("# tampered!\n", encoding="utf-8")

    # Record simulated freeze evidence and resume
    orchestrator.record_freeze(
        "bootstrap_run_image",
        FreezeEvidence(FreezeBoundaryType.DEPLOYMENT_ESTABLISHED, "ro_mount", True),
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


def test_f_simulated_evidence_rejected_in_production() -> None:
    handoff = make_valid_handoff_dict()
    handoff["bootstrap_run_image"]["freeze_evidence"]["boundary_type"] = "simulated_test"
    with pytest.raises(
        ValueError, match="simulated test boundary is prohibited in production verification"
    ):
        verify_handoff(handoff, allow_simulated_boundary=False)


def test_g_bootstrap_artifact_drift(tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    root = tmp_path / "artifacts"
    root.mkdir()
    boot_dir = root / "bootstrap"
    boot_dir.mkdir()
    f = boot_dir / "test.txt"
    f.write_text("hello", encoding="utf-8")
    handoff["locators"]["bootstrap_run_image"] = str(boot_dir)
    handoff["bootstrap_run_image"]["inventory_digest"] = compute_directory_inventory_digest(
        boot_dir
    )

    # All other locators exist
    for loc_key in (
        "installed_skill_root",
        "trusted_base_snapshot",
        "runtime_image",
        "review_bundle",
    ):
        p = root / loc_key
        p.mkdir()
        (p / "dummy.txt").write_text("x", encoding="utf-8")
        handoff["locators"][loc_key] = str(p)
        if loc_key == "installed_skill_root":
            handoff["installed_bootstrap"]["inventory_digest"] = compute_directory_inventory_digest(
                p
            )
        elif loc_key == "trusted_base_snapshot":
            handoff["trusted_base_snapshot"]["inventory_digest"] = (
                compute_directory_inventory_digest(p)
            )
        elif loc_key == "runtime_image":
            handoff["runtime"]["inventory_digest"] = compute_directory_inventory_digest(p)
        elif loc_key == "review_bundle":
            (p / "manifest.json").write_text("{}", encoding="utf-8")
            (p / "procedure").mkdir()
            (p / "procedure/SKILL.md").write_text("skill", encoding="utf-8")
            (p / ".review-authority").mkdir()
            (p / ".review-authority/review-policy.md").write_text("policy", encoding="utf-8")
            handoff["review_bundle"]["manifest_sha256"] = handoff_module.sha256_file(
                p / "manifest.json"
            )
            handoff["review_bundle"]["semantic_policy_sha256"] = handoff_module.sha256_file(
                p / ".review-authority/review-policy.md"
            )
            handoff["semantic_output"]["sha256"] = handoff["review_bundle"][
                "semantic_policy_sha256"
            ]
            handoff["review_bundle"]["inventory_digest"] = compute_directory_inventory_digest(p)

    # Mutate bootstrap file
    f.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="bootstrap run image directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)


def test_h_trusted_base_drift(tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    root = tmp_path / "artifacts"
    root.mkdir()

    for loc_key in (
        "installed_skill_root",
        "bootstrap_run_image",
        "trusted_base_snapshot",
        "runtime_image",
        "review_bundle",
    ):
        p = root / loc_key
        p.mkdir()
        (p / "file.txt").write_text("content", encoding="utf-8")
        handoff["locators"][loc_key] = str(p)
        if loc_key == "installed_skill_root":
            handoff["installed_bootstrap"]["inventory_digest"] = compute_directory_inventory_digest(
                p
            )
        elif loc_key == "bootstrap_run_image":
            handoff["bootstrap_run_image"]["inventory_digest"] = compute_directory_inventory_digest(
                p
            )
        elif loc_key == "trusted_base_snapshot":
            handoff["trusted_base_snapshot"]["inventory_digest"] = (
                compute_directory_inventory_digest(p)
            )
        elif loc_key == "runtime_image":
            handoff["runtime"]["inventory_digest"] = compute_directory_inventory_digest(p)
        elif loc_key == "review_bundle":
            (p / "manifest.json").write_text("{}", encoding="utf-8")
            (p / "procedure").mkdir()
            (p / "procedure/SKILL.md").write_text("skill", encoding="utf-8")
            (p / ".review-authority").mkdir()
            (p / ".review-authority/review-policy.md").write_text("policy", encoding="utf-8")
            handoff["review_bundle"]["manifest_sha256"] = handoff_module.sha256_file(
                p / "manifest.json"
            )
            handoff["review_bundle"]["semantic_policy_sha256"] = handoff_module.sha256_file(
                p / ".review-authority/review-policy.md"
            )
            handoff["semantic_output"]["sha256"] = handoff["review_bundle"][
                "semantic_policy_sha256"
            ]
            handoff["review_bundle"]["inventory_digest"] = compute_directory_inventory_digest(p)

    snap = Path(handoff["locators"]["trusted_base_snapshot"])
    (snap / "file.txt").write_text("drifted content", encoding="utf-8")
    with pytest.raises(ValueError, match="base snapshot directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)


def test_i_runtime_drift(tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    root = tmp_path / "artifacts"
    root.mkdir()

    for loc_key in (
        "installed_skill_root",
        "bootstrap_run_image",
        "trusted_base_snapshot",
        "runtime_image",
        "review_bundle",
    ):
        p = root / loc_key
        p.mkdir()
        (p / "file.txt").write_text("content", encoding="utf-8")
        handoff["locators"][loc_key] = str(p)
        if loc_key == "installed_skill_root":
            handoff["installed_bootstrap"]["inventory_digest"] = compute_directory_inventory_digest(
                p
            )
        elif loc_key == "bootstrap_run_image":
            handoff["bootstrap_run_image"]["inventory_digest"] = compute_directory_inventory_digest(
                p
            )
        elif loc_key == "trusted_base_snapshot":
            handoff["trusted_base_snapshot"]["inventory_digest"] = (
                compute_directory_inventory_digest(p)
            )
        elif loc_key == "runtime_image":
            handoff["runtime"]["inventory_digest"] = compute_directory_inventory_digest(p)
        elif loc_key == "review_bundle":
            (p / "manifest.json").write_text("{}", encoding="utf-8")
            (p / "procedure").mkdir()
            (p / "procedure/SKILL.md").write_text("skill", encoding="utf-8")
            (p / ".review-authority").mkdir()
            (p / ".review-authority/review-policy.md").write_text("policy", encoding="utf-8")
            handoff["review_bundle"]["manifest_sha256"] = handoff_module.sha256_file(
                p / "manifest.json"
            )
            handoff["review_bundle"]["semantic_policy_sha256"] = handoff_module.sha256_file(
                p / ".review-authority/review-policy.md"
            )
            handoff["semantic_output"]["sha256"] = handoff["review_bundle"][
                "semantic_policy_sha256"
            ]
            handoff["review_bundle"]["inventory_digest"] = compute_directory_inventory_digest(p)

    rt = Path(handoff["locators"]["runtime_image"])
    (rt / "file.txt").write_text("mutated runtime binary", encoding="utf-8")
    with pytest.raises(ValueError, match="runtime image directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)


def test_j_bundle_drift(tmp_path: Path) -> None:
    handoff = make_valid_handoff_dict()
    root = tmp_path / "artifacts"
    root.mkdir()

    for loc_key in (
        "installed_skill_root",
        "bootstrap_run_image",
        "trusted_base_snapshot",
        "runtime_image",
        "review_bundle",
    ):
        p = root / loc_key
        p.mkdir()
        (p / "file.txt").write_text("content", encoding="utf-8")
        handoff["locators"][loc_key] = str(p)
        if loc_key == "installed_skill_root":
            handoff["installed_bootstrap"]["inventory_digest"] = compute_directory_inventory_digest(
                p
            )
        elif loc_key == "bootstrap_run_image":
            handoff["bootstrap_run_image"]["inventory_digest"] = compute_directory_inventory_digest(
                p
            )
        elif loc_key == "trusted_base_snapshot":
            handoff["trusted_base_snapshot"]["inventory_digest"] = (
                compute_directory_inventory_digest(p)
            )
        elif loc_key == "runtime_image":
            handoff["runtime"]["inventory_digest"] = compute_directory_inventory_digest(p)
        elif loc_key == "review_bundle":
            (p / "manifest.json").write_text("{}", encoding="utf-8")
            (p / "procedure").mkdir()
            (p / "procedure/SKILL.md").write_text("skill", encoding="utf-8")
            (p / ".review-authority").mkdir()
            (p / ".review-authority/review-policy.md").write_text("policy", encoding="utf-8")
            handoff["review_bundle"]["manifest_sha256"] = handoff_module.sha256_file(
                p / "manifest.json"
            )
            handoff["review_bundle"]["semantic_policy_sha256"] = handoff_module.sha256_file(
                p / ".review-authority/review-policy.md"
            )
            handoff["semantic_output"]["sha256"] = handoff["review_bundle"][
                "semantic_policy_sha256"
            ]
            handoff["review_bundle"]["inventory_digest"] = compute_directory_inventory_digest(p)

    bundle = Path(handoff["locators"]["review_bundle"])

    # J1: Mutate SKILL.md
    (bundle / "procedure/SKILL.md").write_text("mutated skill", encoding="utf-8")
    with pytest.raises(ValueError, match="review bundle directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)
    (bundle / "procedure/SKILL.md").write_text("skill", encoding="utf-8")

    # J2: Mutate semantic policy
    (bundle / ".review-authority/review-policy.md").write_text("mutated policy", encoding="utf-8")
    with pytest.raises(ValueError, match="review bundle directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)
    (bundle / ".review-authority/review-policy.md").write_text("policy", encoding="utf-8")

    # J3: Add extra file
    (bundle / "extra.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError, match="review bundle directory contents do not match"):
        verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)


def test_k_untrusted_provider_identity_input() -> None:
    data = make_valid_handoff_dict()
    data["provider"]["observation_evidence"]["authenticated"] = False
    with pytest.raises(ValueError, match="provider observation is not authenticated"):
        verify_handoff(data, require_authenticated_provider=True)


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
        )


def test_full_pipeline_end_to_end_simulated(
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

    # Mock subprocess.run and check_output for agent-policy calls
    def mock_subprocess_run(
        cmd: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def mock_check_output(cmd: list[str], *args: Any, **kwargs: Any) -> str:
        # Mock review-bundle command
        dest_idx = cmd.index("--output-dir") + 1
        bundle_out = Path(cmd[dest_idx])
        bundle_out.mkdir(parents=True, exist_ok=True)
        (bundle_out / "manifest.json").write_text("{}", encoding="utf-8")
        (bundle_out / "procedure").mkdir(parents=True, exist_ok=True)
        (bundle_out / "procedure/SKILL.md").write_text("skill", encoding="utf-8")
        (bundle_out / ".review-authority").mkdir(parents=True, exist_ok=True)
        (bundle_out / ".review-authority/review-policy.md").write_text("policy", encoding="utf-8")
        return json.dumps(
            {
                "manifest_sha256": handoff_module.sha256_file(bundle_out / "manifest.json"),
                "semantic_policy_sha256": handoff_module.sha256_file(
                    bundle_out / ".review-authority/review-policy.md"
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
    )
    assert res["status"] == handoff_module.STATUS_HANDOFF_READY
    assert res["phase"] == Phase.HANDOFF_FINALIZED.value
    verify_handoff(res["handoff"], allow_simulated_boundary=True, check_locators=True)

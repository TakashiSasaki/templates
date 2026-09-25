from __future__ import annotations

import json
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
    check_drift,
    format_reviewer_packet,
    prepare_handoff,
    verify_handoff,
)

ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "scripts/install_agent_policy_skill.py"
SKILL_SOURCE_PATH = ROOT / "skills/agent-policy"

installer = handoff_module.load_module_from_path("installer_test", INSTALLER_PATH)


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
            },
            "skill_source": {
                "repository": "TakashiSasaki/templates",
                "revision": valid_sha("4"),
                "path": "skills/agent-policy",
            },
            "attestation": {
                "sha256": valid_sha256("a"),
                "entries_sha256": valid_sha256("e"),
            },
            "inventory_sha256": valid_sha256("0"),
        },
        "bootstrap_run_image": {
            "inventory_sha256": valid_sha256("b"),
            "freeze": {
                "boundary_type": "deployment_established",
                "mechanism": "container_read_only_bind_mount",
                "verified_post_freeze": True,
            },
        },
        "trusted_base_snapshot": {
            "commit": base_commit,
            "tree": base_tree,
            "inventory_sha256": valid_sha256("1"),
            "freeze": {
                "boundary_type": "deployment_established",
                "mechanism": "container_read_only_bind_mount",
                "verified_post_freeze": True,
            },
        },
        "runtime": {
            "repository": "TakashiSasaki/templates",
            "revision": valid_sha("5"),
            "lock_sha256": valid_sha256("2"),
            "python": "cpython-3.12",
            "platform": "linux-aarch64",
            "attestation_sha256": valid_sha256("3"),
            "image_inventory_sha256": valid_sha256("4"),
            "freeze": {
                "boundary_type": "deployment_established",
                "mechanism": "container_read_only_bind_mount",
                "verified_post_freeze": True,
            },
        },
        "review_bundle": {
            "bundle_format": 1,
            "manifest_sha256": manifest_digest,
            "procedure_skill_name": "pr-review",
            "procedure_skill_sha256": valid_sha256("5"),
            "procedure_references": {
                "procedure/references/github-pull-request-review-api.md": valid_sha256("6"),
            },
            "semantic_policy_sha256": semantic_digest,
            "freeze": {
                "boundary_type": "deployment_established",
                "mechanism": "container_read_only_bind_mount",
                "verified_post_freeze": True,
            },
        },
        "semantic_output": {
            "path": ".review-authority/review-policy.md",
            "renderer": "policy-context-md",
            "context": "review",
            "sha256": semantic_digest,
        },
        "locators": {
            "installed_skill_root": "/opt/agent-policy",
            "installation_attestation_path": "/var/run/attestation.json",
            "bootstrap_run_image_dir": "/var/run/bootstrap-image",
            "trusted_base_snapshot_dir": "/var/run/base-snapshot",
            "runtime_attestation_path": "/var/run/runtime-attestation.json",
            "runtime_image_dir": "/var/run/runtime-image",
            "review_bundle_dir": "/var/run/review-bundle",
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


@pytest.mark.parametrize(
    ("path", "bad_value"),
    [
        (["exact_base", "commit"], "main"),
        (["exact_base", "commit"], "12345"),
        (["exact_base", "commit"], "A" * 40),
        (["exact_base", "tree"], "HEAD"),
        (["runtime", "revision"], "v1.0.0"),
        (["review_bundle", "manifest_sha256"], "short"),
        (["review_bundle", "manifest_sha256"], "Z" * 64),
        (["semantic_output", "sha256"], "not-a-hash"),
    ],
)
def test_handoff_rejects_malformed_shas_and_digests(path: list[str], bad_value: str) -> None:
    data = make_valid_handoff_dict()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad_value
    with pytest.raises(ValueError):
        verify_handoff(data)


def test_handoff_rejects_inconsistent_base_commit_or_tree() -> None:
    data = make_valid_handoff_dict()
    data["trusted_base_snapshot"]["commit"] = valid_sha("9")
    with pytest.raises(ValueError, match="base commit mismatch"):
        verify_handoff(data)

    data = make_valid_handoff_dict()
    data["trusted_base_snapshot"]["tree"] = valid_sha("8")
    with pytest.raises(ValueError, match="base tree mismatch"):
        verify_handoff(data)


def test_handoff_rejects_semantic_policy_and_bundle_mismatch() -> None:
    data = make_valid_handoff_dict()
    data["semantic_output"]["sha256"] = valid_sha256("f")
    with pytest.raises(ValueError, match="semantic_output sha256 does not match"):
        verify_handoff(data)


def test_handoff_rejects_unsupported_semantic_renderer() -> None:
    data = make_valid_handoff_dict()
    data["semantic_output"]["renderer"] = "agents-md"
    with pytest.raises(ValueError, match="renderer must be policy-context-md"):
        verify_handoff(data)


def test_handoff_rejects_unverified_freeze_state() -> None:
    for artifact in ["bootstrap_run_image", "trusted_base_snapshot", "runtime", "review_bundle"]:
        data = make_valid_handoff_dict()
        data[artifact]["freeze"]["verified_post_freeze"] = False
        with pytest.raises(ValueError, match="was not verified post-freeze"):
            verify_handoff(data)


def test_handoff_rejects_simulated_freeze_boundary_in_production_mode() -> None:
    data = make_valid_handoff_dict()
    data["review_bundle"]["freeze"]["boundary_type"] = FreezeBoundaryType.SIMULATED_TEST.value
    with pytest.raises(ValueError, match="simulated freeze boundary, prohibited in production"):
        verify_handoff(data, allow_simulated_boundary=False)

    verify_handoff(data, allow_simulated_boundary=True)


def test_handoff_locator_path_moves_do_not_invalidate_identity() -> None:
    data = make_valid_handoff_dict()
    data["locators"]["review_bundle_dir"] = "/different/path/review-bundle"
    verify_handoff(data, check_locators=False)


def test_drift_detection_invalidates_complete_authority_on_base_movement() -> None:
    data = make_valid_handoff_dict()
    disp = check_drift(
        data,
        current_base_commit=valid_sha("9"),
        current_base_tree=data["exact_base"]["tree"],
        current_head_commit=valid_sha("0"),
        initial_head_commit=valid_sha("0"),
    )
    assert disp.base_drift is True
    assert disp.invalidates_authority is True
    assert disp.invalidates_head_evidence is True

    disp_tree = check_drift(
        data,
        current_base_commit=data["exact_base"]["commit"],
        current_base_tree=valid_sha("9"),
        current_head_commit=valid_sha("0"),
        initial_head_commit=valid_sha("0"),
    )
    assert disp_tree.base_drift is True
    assert disp_tree.invalidates_authority is True
    assert disp_tree.invalidates_head_evidence is True


def test_drift_detection_preserves_authority_on_head_only_movement() -> None:
    data = make_valid_handoff_dict()
    disp = check_drift(
        data,
        current_base_commit=data["exact_base"]["commit"],
        current_base_tree=data["exact_base"]["tree"],
        current_head_commit=valid_sha("7"),
        initial_head_commit=valid_sha("6"),
    )
    assert disp.base_drift is False
    assert disp.head_drift is True
    assert disp.invalidates_authority is False
    assert disp.invalidates_head_evidence is True


def test_drift_detection_clean_when_no_movement() -> None:
    data = make_valid_handoff_dict()
    disp = check_drift(
        data,
        current_base_commit=data["exact_base"]["commit"],
        current_base_tree=data["exact_base"]["tree"],
        current_head_commit=valid_sha("6"),
        initial_head_commit=valid_sha("6"),
    )
    assert disp.base_drift is False
    assert disp.head_drift is False
    assert disp.invalidates_authority is False
    assert disp.invalidates_head_evidence is False


def test_format_reviewer_packet_contains_all_mandatory_elements() -> None:
    data = make_valid_handoff_dict()
    packet = format_reviewer_packet(
        data,
        handoff_path="/path/to/handoff.json",
        handoff_sha256=valid_sha256("0"),
        head_commit=valid_sha("9"),
    )
    assert "TRUSTED REVIEW BOOTSTRAP REVIEWER PACKET" in packet
    assert data["provider"]["repository"]["id"] in packet
    assert data["exact_base"]["commit"] in packet
    assert valid_sha("9") in packet
    assert data["locators"]["review_bundle_dir"] in packet
    assert "Consume ONLY the procedure and semantic authority" in packet
    assert "Do not select, discover, reproduce, or verify review procedure" in packet


def test_installer_attestation_adversarial_rejections(tmp_path: Path) -> None:
    target = tmp_path / "skill"
    scripts_dir = target / "scripts"
    scripts_dir.mkdir(parents=True)
    (target / "SKILL.md").write_text("---\nname: agent-policy\n---\n", encoding="utf-8")
    (target / "runtime-manifest.json").write_text("{}\n", encoding="utf-8")
    (scripts_dir / "install.py").write_text("pass\n", encoding="utf-8")

    attestation_path = tmp_path / "trust/attestation.json"
    attestation_path.parent.mkdir()
    installer.write_installation_attestation(
        target,
        attestation_path,
        installer_revision=valid_sha("1"),
    )

    with pytest.raises(RuntimeError, match="installer identity does not match"):
        installer.verify_installation_attestation(
            target,
            attestation_path,
            installer_revision=valid_sha("2"),
        )

    (target / "SKILL.md").write_text("drift", encoding="utf-8")
    with pytest.raises(RuntimeError, match="does not match installed skill tree"):
        installer.verify_installation_attestation(
            target,
            attestation_path,
            installer_revision=valid_sha("1"),
        )


def test_prepare_handoff_rejects_runtime_override(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="caller-selected runtime revision override is forbidden"):
        prepare_handoff(
            object_repository=tmp_path,
            base_commit=valid_sha("1"),
            provider_identity={
                "name": "github",
                "repository": {"id": "1", "name_with_owner": "o/r"},
                "pull_request": {"id": "1", "number": 1},
            },
            installed_skill_root=tmp_path,
            installation_attestation_path=tmp_path / "att.json",
            installer_revision=valid_sha("2"),
            work_dir=tmp_path / "work",
            runtime_override_attempt=valid_sha("3"),
        )


def test_prepare_handoff_rejects_proposed_head_as_base(tmp_path: Path) -> None:
    same_commit = valid_sha("1")
    with pytest.raises(ValueError, match="base commit and proposed head must be distinct"):
        prepare_handoff(
            object_repository=tmp_path,
            base_commit=same_commit,
            proposed_head=same_commit,
            provider_identity={
                "name": "github",
                "repository": {"id": "1", "name_with_owner": "o/r"},
                "pull_request": {"id": "1", "number": 1},
            },
            installed_skill_root=tmp_path,
            installation_attestation_path=tmp_path / "att.json",
            installer_revision=valid_sha("2"),
            work_dir=tmp_path / "work",
        )


def test_prepare_handoff_stops_with_capability_blocked_when_no_freeze_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_dir = tmp_path / "work"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    monkeypatch.setattr(
        handoff_module,
        "resolve_base_tree",
        lambda _git, _repo, _commit: valid_sha("2"),
    )

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.load_installation_attestation = lambda path: {
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
        "installation": {"entries": {}},
    }
    mock_installer.materialize_run_image = lambda target, dest, att, **kwargs: dest.mkdir(
        parents=True, exist_ok=True
    )
    monkeypatch.setattr(handoff_module, "load_module_from_path", lambda name, path: mock_installer)

    mock_review_base = ModuleType("mock_review_base")
    mock_review_base.materialize = lambda git, repo, base, dest: dest.mkdir(
        parents=True, exist_ok=True
    )
    mock_runtime_image = ModuleType("mock_runtime_image")
    mock_runtime_image.create_attestation = lambda snap, path: path.write_text(
        "{}", encoding="utf-8"
    )
    mock_runtime_image.materialize_image = lambda snap, att, dest: dest.mkdir(
        parents=True, exist_ok=True
    )
    mock_runtime_image.venv_python = lambda dest: Path(sys.executable)
    mock_runtime_image.trusted_environment = lambda: {}

    def custom_load_module(name: str, path: Path) -> ModuleType:
        if "review_base" in str(path):
            return mock_review_base
        if "runtime_image" in str(path):
            return mock_runtime_image
        return mock_installer

    monkeypatch.setattr(handoff_module, "load_module_from_path", custom_load_module)

    def mock_materialize_base(git: Path, repo: Path, base: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / ".agent-policy.lock").write_text(
            yaml.safe_dump(
                {"toolchain": {"repository": "TakashiSasaki/templates", "revision": valid_sha("3")}}
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

    mock_review_base.materialize = mock_materialize_base

    def mock_sub_run(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "review-bundle" in cmd and "materialize" in cmd:
            dest = Path(cmd[cmd.index("--destination") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, stdout="materialized", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_sub_run)

    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    (skill_root / "marker").write_text("ok", encoding="utf-8")
    att_path = tmp_path / "att.json"
    att_path.write_text("{}", encoding="utf-8")

    result = prepare_handoff(
        object_repository=repo_dir,
        base_commit=valid_sha("1"),
        provider_identity={
            "name": "github",
            "repository": {"id": "R_1", "name_with_owner": "o/r"},
            "pull_request": {"id": "PR_1", "number": 100},
        },
        installed_skill_root=skill_root,
        installation_attestation_path=att_path,
        installer_revision=valid_sha("1"),
        work_dir=work_dir,
        freeze_command=None,
        simulate_freeze_for_test=False,
    )

    assert result["status"] == handoff_module.STATUS_FREEZE_BLOCKED
    assert "materialized_artifacts" in result
    assert "sufficient_capability" in result


def test_end_to_end_operational_handoff_with_simulated_freeze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_dir = tmp_path / "work"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    base_commit = valid_sha("1")
    base_tree = valid_sha("2")
    runtime_rev = valid_sha("3")
    installer_rev = valid_sha("4")
    skill_rev = valid_sha("5")

    monkeypatch.setattr(
        handoff_module,
        "resolve_base_tree",
        lambda _git, _repo, _commit: base_tree,
    )

    mock_installer = ModuleType("mock_installer")
    mock_installer.verify_installation_attestation = lambda *args, **kwargs: None
    mock_installer.load_installation_attestation = lambda path: {
        "installer": {
            "repository": "TakashiSasaki/templates",
            "revision": installer_rev,
            "path": "scripts/install_agent_policy_skill.py",
        },
        "skill_source": {
            "repository": "TakashiSasaki/templates",
            "revision": skill_rev,
            "path": "skills/agent-policy",
        },
        "installation": {"entries": {"SKILL.md": {"type": "file", "sha256": valid_sha256("a")}}},
    }
    mock_installer.materialize_run_image = lambda target, dest, att, **kwargs: dest.mkdir(
        parents=True, exist_ok=True
    )
    mock_installer.verify_run_image = lambda *args, **kwargs: None

    mock_review_base = ModuleType("mock_review_base")

    def mock_materialize_base(git: Path, repo: Path, base: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / ".agent-policy.lock").write_text(
            yaml.safe_dump(
                {"toolchain": {"repository": "TakashiSasaki/templates", "revision": runtime_rev}}
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

    mock_review_base.materialize = mock_materialize_base
    mock_review_base.verify = lambda git, repo, base, dest: {"status": "VERIFIED_FROZEN_INPUT"}

    mock_runtime_image = ModuleType("mock_runtime_image")
    mock_runtime_image.create_attestation = lambda snap, path: path.write_text(
        "{}", encoding="utf-8"
    )
    mock_runtime_image.materialize_image = lambda snap, att, dest: dest.mkdir(
        parents=True, exist_ok=True
    )
    mock_runtime_image.venv_python = lambda dest: Path(sys.executable)
    mock_runtime_image.trusted_environment = lambda: {}
    mock_runtime_image.verify_image = lambda snap, att, dest, **kwargs: {
        "runtime": {
            "lock_sha256": valid_sha256("b"),
            "python": "cpython-3.12",
            "platform": "linux-aarch64",
        }
    }

    def custom_load_module(name: str, path: Path) -> ModuleType:
        if "review_base" in str(path):
            return mock_review_base
        if "runtime_image" in str(path):
            return mock_runtime_image
        return mock_installer

    monkeypatch.setattr(handoff_module, "load_module_from_path", custom_load_module)

    def mock_sub_run(cmd: list[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "review-bundle" in cmd and "materialize" in cmd:
            dest = Path(cmd[cmd.index("--destination") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "manifest.json").write_text(json.dumps({"bundle_format": 1}), encoding="utf-8")
            proc = dest / "procedure"
            proc.mkdir()
            (proc / "SKILL.md").write_text("procedure skill\n", encoding="utf-8")
            (proc / "ref.md").write_text("procedure ref\n", encoding="utf-8")
            sem = dest / "semantic"
            sem.mkdir()
            (sem / "review-policy.md").write_text("semantic rule\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="materialized", stderr="")
        if "review-bundle" in cmd and "verify" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="verified", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_sub_run)

    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    (skill_root / "SKILL.md").write_text("installed skill\n", encoding="utf-8")
    att_path = tmp_path / "att.json"
    att_path.write_text("{}", encoding="utf-8")

    result = prepare_handoff(
        object_repository=repo_dir,
        base_commit=base_commit,
        proposed_head=valid_sha("9"),
        provider_identity={
            "name": "github",
            "repository": {"id": "R_test123", "name_with_owner": "TakashiSasaki/templates"},
            "pull_request": {"id": "PR_test456", "number": 1031},
        },
        installed_skill_root=skill_root,
        installation_attestation_path=att_path,
        installer_revision=installer_rev,
        work_dir=work_dir,
        freeze_command=None,
        simulate_freeze_for_test=True,
    )

    assert result["status"] == handoff_module.STATUS_HANDOFF_READY
    handoff = result["handoff"]

    verify_handoff(handoff, allow_simulated_boundary=True, check_locators=True)

    assert handoff["exact_base"]["commit"] == base_commit
    assert handoff["exact_base"]["tree"] == base_tree
    assert handoff["runtime"]["revision"] == runtime_rev
    assert handoff["semantic_output"]["renderer"] == "policy-context-md"
    assert handoff["bootstrap_run_image"]["freeze"]["boundary_type"] == "simulated_test"

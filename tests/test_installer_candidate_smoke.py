from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/smoke_test_agent_policy_installer_candidate.py"
WORKFLOW = ROOT / ".github/workflows/installer-candidate.yml"
INSTALLER = ROOT / "scripts/install_agent_policy_skill.py"


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke = load_script(SCRIPT, "smoke_installer_candidate")
installer = load_script(INSTALLER, "installer_candidate_pin_test")


def test_installer_candidate_pins_qualified_skill_source() -> None:
    expected = "20cdbc720249516e3d30fc93e050391b81eaa6b4"
    assert smoke.EXPECTED_SKILL_SOURCE_REVISION == expected
    assert installer.SKILL_SOURCE_REVISION == expected


def test_remote_installer_url_requires_exact_revision() -> None:
    revision = "b" * 40
    assert smoke.raw_installer_url(revision) == (
        "https://raw.githubusercontent.com/TakashiSasaki/templates/"
        f"{revision}/scripts/install_agent_policy_skill.py"
    )
    for invalid in ("policy", "main", "deadbeef"):
        with pytest.raises(ValueError, match="full lowercase commit SHA"):
            smoke.raw_installer_url(invalid)


def test_remote_installer_command_binds_candidate_and_attestation(
    tmp_path: Path,
) -> None:
    revision = "c" * 40
    target = tmp_path / "installed" / "agent-policy"
    attestation = tmp_path / "trust" / "installation.json"
    command = smoke.remote_installer_command(revision, target, attestation)

    assert command[:3] == [sys.executable, "-I", "-c"]
    assert smoke.raw_installer_url(revision) in command[3]
    assert command[4:] == [
        str(target),
        "--installer-revision",
        revision,
        "--attestation",
        str(attestation),
    ]


def test_installer_candidate_binds_i_s_and_consumer_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = "d" * 40
    stable = json.loads(
        (ROOT / "release/toolchain.json").read_text(encoding="utf-8")
    )["toolchain"]
    observed: dict[str, object] = {"operations": []}

    def verify_installation_attestation(
        target: Path,
        attestation: Path,
        *,
        installer_revision: str,
    ) -> None:
        observed["verified"] = (target, attestation, installer_revision)

    fake_installer = SimpleNamespace(
        SKILL_SOURCE_REVISION=smoke.EXPECTED_SKILL_SOURCE_REVISION,
        verify_installation_attestation=verify_installation_attestation,
    )
    monkeypatch.setattr(smoke, "load_installer", lambda: fake_installer)

    def consumer_configuration(toolchain: object) -> dict[str, object]:
        return {"schema_version": 2, "toolchain": toolchain}

    def run_installed(
        _installed: Path,
        repository: Path,
        _environment: dict[str, str],
        operation: str,
    ) -> subprocess.CompletedProcess[str]:
        operations = observed["operations"]
        assert isinstance(operations, list)
        operations.append(operation)
        if operation == "render":
            generated = (
                repository
                / ".agents/skills/orchestrate-repository-change/SKILL.md"
            )
            generated.parent.mkdir(parents=True)
            generated.write_text(
                "<!-- source-skill: orchestrate-repository-change -->\n",
                encoding="utf-8",
            )
            (repository / ".agent-policy.lock").write_text(
                "lock_version: 1\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess([operation], 0, "", "")

    def require_success(
        result: subprocess.CompletedProcess[str],
        _operation: str,
    ) -> None:
        assert result.returncode == 0

    def verify_generated_lock(
        lock: Path,
        installed: Path,
        toolchain: object,
    ) -> None:
        observed["lock"] = (lock, installed, toolchain)

    fake_skill_smoke = SimpleNamespace(
        SKILL_NAME="orchestrate-repository-change",
        consumer_configuration=consumer_configuration,
        run_installed=run_installed,
        require_success=require_success,
        verify_generated_lock=verify_generated_lock,
    )
    monkeypatch.setattr(smoke, "load_skill_source_smoke", lambda: fake_skill_smoke)

    def fake_run(
        command: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        observed["remote_command"] = command
        target = Path(command[4])
        (target / "scripts").mkdir(parents=True)
        (target / "scripts/run.py").write_text("# runner\n", encoding="utf-8")
        (target / "runtime-manifest.json").write_text(
            json.dumps({"toolchain": stable}) + "\n",
            encoding="utf-8",
        )
        attestation = Path(command[command.index("--attestation") + 1])
        attestation.parent.mkdir(parents=True)
        attestation.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "installer": {
                        "repository": "TakashiSasaki/templates",
                        "revision": revision,
                        "path": "scripts/install_agent_policy_skill.py",
                    },
                    "skill_source": {
                        "repository": "TakashiSasaki/templates",
                        "revision": smoke.EXPECTED_SKILL_SOURCE_REVISION,
                        "path": "skills/agent-policy",
                    },
                    "installation": {"root": str(target), "entries": {"x": {}}},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)
    smoke.run_candidate(revision)

    remote = observed["remote_command"]
    assert isinstance(remote, list)
    assert smoke.raw_installer_url(revision) in remote[3]
    assert observed["operations"] == ["render", "check"]
    verified = observed["verified"]
    assert isinstance(verified, tuple)
    assert verified[2] == revision
    lock = observed["lock"]
    assert isinstance(lock, tuple)
    assert lock[2] == stable


def test_installer_workflow_is_exact_head_path_scoped_and_cross_platform() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "name: Policy installer candidate" in workflow
    assert "pull_request:" in workflow
    assert "push:" not in workflow
    assert "paths:" in workflow
    assert "scripts/install_agent_policy_skill.py" in workflow
    assert "github.event.pull_request.head.sha" in workflow
    assert "Check out exact installer candidate" in workflow
    assert "smoke_test_agent_policy_installer_candidate.py" in workflow
    assert "ubuntu-24.04" in workflow
    assert "windows-2022" in workflow

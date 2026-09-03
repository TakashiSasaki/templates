from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/smoke_test_agent_policy_skill_source.py"
WORKFLOW = ROOT / ".github/workflows/runtime-distribution.yml"
SKILL_ROOT = ROOT / "skills" / "agent-policy"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("smoke_skill_source_candidate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke = load_script()


def test_candidate_revision_must_be_immutable() -> None:
    revision = "a" * 40
    assert smoke.require_revision(revision) == revision
    for invalid in ("policy", "main", "abc123"):
        with pytest.raises(ValueError, match="full lowercase commit SHA"):
            smoke.require_revision(invalid)


def test_consumer_configuration_enables_only_orchestration_skill() -> None:
    toolchain = {
        "repository": "TakashiSasaki/templates",
        "revision": "a" * 40,
    }
    config = smoke.consumer_configuration(toolchain)
    assert config["toolchain"] == toolchain
    assert config["contexts"] == {
        "coding": {
            "profiles": ["core"],
            "project_policy": {"files": []},
        }
    }
    assert config["skills"] == {"enabled": ["orchestrate-repository-change"]}


def test_generated_lock_requires_exact_toolchain_identity(tmp_path: Path) -> None:
    stable = {
        "repository": "TakashiSasaki/templates",
        "revision": "a" * 40,
    }
    lock = tmp_path / ".agent-policy.lock"
    lock.write_text(
        "lock_version: 1\n"
        "toolchain:\n"
        "  repository: TakashiSasaki/templates\n"
        f"  revision: {'b' * 40}\n"
        f"# unrelated stable revision mention: {stable['revision']}\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="complete stable toolchain identity"):
        smoke.verify_generated_lock(lock, SKILL_ROOT, stable)


def test_generated_lock_requires_supported_schema_version(tmp_path: Path) -> None:
    stable = {
        "repository": "TakashiSasaki/templates",
        "revision": "a" * 40,
    }
    lock = tmp_path / ".agent-policy.lock"
    lock.write_text(
        "lock_version: 2\n"
        "toolchain:\n"
        "  repository: TakashiSasaki/templates\n"
        f"  revision: {stable['revision']}\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="schema version is unsupported"):
        smoke.verify_generated_lock(lock, SKILL_ROOT, stable)


def test_generated_lock_accepts_exact_stable_identity(tmp_path: Path) -> None:
    stable = {
        "repository": "TakashiSasaki/templates",
        "revision": "a" * 40,
    }
    lock = tmp_path / ".agent-policy.lock"
    lock.write_text(
        "lock_version: 1\n"
        "toolchain:\n"
        "  repository: TakashiSasaki/templates\n"
        f"  revision: {stable['revision']}\n",
        encoding="utf-8",
    )

    smoke.verify_generated_lock(lock, SKILL_ROOT, stable)


def test_candidate_smoke_binds_remote_source_to_stable_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = "b" * 40
    stable = json.loads((ROOT / "release/toolchain.json").read_text(encoding="utf-8"))[
        "toolchain"
    ]
    observed: dict[str, object] = {"commands": []}

    def download_archive(selected: str) -> bytes:
        observed["revision"] = selected
        return b"candidate-archive"

    def install_downloaded_skill(
        archive: bytes,
        installed: Path,
        *,
        replace: bool,
    ) -> None:
        assert archive == b"candidate-archive"
        assert replace is False
        (installed / "scripts").mkdir(parents=True)
        (installed / "scripts/run.py").write_text("# run\n", encoding="utf-8")
        (installed / "runtime-manifest.json").write_text(
            json.dumps({"toolchain": stable}) + "\n",
            encoding="utf-8",
        )

    fake_installer = SimpleNamespace(
        download_archive=download_archive,
        install_downloaded_skill=install_downloaded_skill,
    )
    fake_runtime = SimpleNamespace(
        lock_toolchain=lambda _path: (
            "TakashiSasaki/templates",
            stable["revision"],
        )
    )
    monkeypatch.setattr(smoke, "load_installer", lambda: fake_installer)
    monkeypatch.setattr(smoke, "load_installed_runtime", lambda _path: fake_runtime)

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        operation = command[-1]
        observed["commands"].append(operation)
        repository = Path(command[command.index("--repository") + 1])
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
            lock_text = (
                "lock_version: 1\n"
                "toolchain:\n"
                "  repository: TakashiSasaki/templates\n"
                f"  revision: {stable['revision']}\n"
            )
            (repository / ".agent-policy.lock").write_text(
                lock_text,
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)
    smoke.run_candidate(revision)
    assert observed["revision"] == revision
    assert observed["commands"] == ["render", "check"]


def test_runtime_workflow_qualifies_exact_head_on_linux_and_windows() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "skill-source-candidate:" in workflow
    assert "github.event.pull_request.head.sha" in workflow
    assert "Check out exact skill-source candidate" in workflow
    assert "smoke_test_agent_policy_skill_source.py" in workflow
    assert "ubuntu-24.04" in workflow
    assert "windows-2022" in workflow
    assert "SKILL_SOURCE_RESULT" in workflow
    assert 'test "$SKILL_SOURCE_RESULT" = success' in workflow
    assert 'test "$SKILL_SOURCE_RESULT" = skipped' in workflow

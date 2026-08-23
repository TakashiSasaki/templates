from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/agent-policy"
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, relative: str) -> ModuleType:
    path = SKILL_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_script("agent_policy_skill_runtime", "scripts/runtime.py")
bootstrap = load_script("agent_policy_skill_bootstrap", "scripts/bootstrap.py")
runner = load_script("agent_policy_skill_runner", "scripts/run.py")
installer = load_script("agent_policy_skill_install", "scripts/install.py")
uninstaller = load_script("agent_policy_skill_uninstall", "scripts/uninstall.py")


def stable_toolchain() -> dict[str, str]:
    release = json.loads((ROOT / "release/toolchain.json").read_text(encoding="utf-8"))
    toolchain = release["toolchain"]
    assert isinstance(toolchain, dict)
    return toolchain


def identity(
    revision: str = "a" * 40,
    lock_sha256: str = "b" * 64,
    python: str = "3.12",
    platform: str = "linux-x86_64",
) -> object:
    return runtime.RuntimeIdentity(
        "TakashiSasaki/templates",
        revision,
        lock_sha256,
        python,
        platform,
    )


def write_fake_runtime_entrypoints(target: Path, executable_name: str) -> None:
    python = runtime.venv_python(target)
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("cached-python", encoding="utf-8")
    executable = runtime.executable_path(target, executable_name)
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("cached-executable", encoding="utf-8")


def test_single_skill_layout_and_release_pin() -> None:
    expected = {
        "README.md",
        "SKILL.md",
        "runtime-manifest.json",
        "scripts/bootstrap.py",
        "scripts/install.py",
        "scripts/run.py",
        "scripts/runtime.py",
        "scripts/uninstall.py",
    }
    actual = {
        path.relative_to(SKILL_ROOT).as_posix()
        for path in SKILL_ROOT.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }
    assert actual == expected

    manifest = runtime.load_manifest()
    assert manifest["toolchain"] == stable_toolchain()
    assert manifest["schema_version"] == 1
    assert manifest["runtime_lock"]["path"] == "requirements-runtime.lock"
    assert "finalize" not in json.dumps(manifest["routes"])


def test_skill_is_the_single_public_repository_entry_point() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "name: agent-policy" in skill
    assert "single repository-facing entry point" in skill
    assert "must never finalize migration" in skill.lower()
    assert ".agent-policy.lock" in skill
    assert "full lowercase 40-character commit SHA" in skill


def test_runtime_lock_digest_matches_promoted_revision_lock() -> None:
    manifest = runtime.load_manifest()
    lock = (ROOT / "requirements-runtime.lock").read_bytes()
    assert hashlib.sha256(lock).hexdigest() == manifest["runtime_lock"]["sha256"]


def test_runtime_lock_parser_requires_exact_unique_distribution_set() -> None:
    parsed = runtime.parse_runtime_lock("Jinja2===3.1.6\nPyYAML===6.0.3\n")
    assert parsed == {"jinja2": "3.1.6", "pyyaml": "6.0.3"}

    with pytest.raises(ValueError, match="not exact"):
        runtime.parse_runtime_lock("Jinja2>=3.1\n")
    with pytest.raises(ValueError, match="duplicated"):
        runtime.parse_runtime_lock("PyYAML===6.0.3\npyyaml===6.0.3\n")


def test_managed_repository_lock_takes_precedence_and_fails_closed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / ".agent-policy.lock").write_text(
        """lock_version: 1
toolchain:
  repository: TakashiSasaki/templates
  revision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
""",
        encoding="utf-8",
    )
    pin = runtime.select_pin(root)
    assert pin.revision == "a" * 40
    assert pin.expected_lock_sha256 is None
    assert pin.project_version is None

    (root / ".agent-policy.lock").write_text(
        """lock_version: 1
toolchain:
  repository: TakashiSasaki/templates
  revision: policy
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="full lowercase commit SHA"):
        runtime.select_pin(root)


def test_managed_lock_toolchain_parser_rejects_nested_and_duplicate_keys(
    tmp_path: Path,
) -> None:
    lock = tmp_path / ".agent-policy.lock"
    lock.write_text(
        """lock_version: 1
toolchain:
  repository: TakashiSasaki/templates
    revision: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
  revision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="flat two-space mapping"):
        runtime.lock_toolchain(lock)

    lock.write_text(
        """lock_version: 1
toolchain:
  repository: TakashiSasaki/templates
  revision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  revision: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicated"):
        runtime.lock_toolchain(lock)


def test_unmanaged_repository_uses_runtime_manifest_pin(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    pin = runtime.select_pin(root)
    assert pin.revision == stable_toolchain()["revision"]
    assert pin.expected_lock_sha256 == runtime.load_manifest()["runtime_lock"]["sha256"]
    assert pin.project_version == "0.1.0"


def test_runtime_identity_separates_revision_lock_python_and_platform() -> None:
    base = identity()
    variants = [
        identity(revision="c" * 40),
        identity(lock_sha256="d" * 64),
        identity(python="3.13"),
        identity(platform="win32-amd64"),
    ]
    assert len({base.digest(), *(item.digest() for item in variants)}) == 5


def test_cli_command_uses_cached_python_module_entrypoint(tmp_path: Path) -> None:
    target = tmp_path / "runtime"
    assert runtime.cli_command(target) == [
        str(runtime.venv_python(target)),
        "-I",
        "-m",
        "agent_policy.cli",
    ]


def test_valid_default_cache_hit_requires_no_network(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pin = runtime.pin_from_manifest(runtime.load_manifest())
    cache_identity = runtime.RuntimeIdentity(
        pin.repository,
        pin.revision,
        pin.expected_lock_sha256,
        runtime.python_token(),
        runtime.platform_token(),
    )
    target = tmp_path / cache_identity.digest()
    target.mkdir(parents=True)
    write_fake_runtime_entrypoints(target, pin.executable)
    runtime.marker_path(target).write_text(
        json.dumps(runtime.expected_marker(cache_identity, pin)),
        encoding="utf-8",
    )

    def network_forbidden(_pin: object) -> bytes:
        raise AssertionError("network must not be used for a valid cache hit")

    monkeypatch.setattr(runtime, "download_runtime_lock", network_forbidden)
    assert runtime.ensure_runtime(pin, root=tmp_path) == target


def test_cached_nondefault_revision_can_be_reused_offline(tmp_path: Path) -> None:
    default = runtime.pin_from_manifest(runtime.load_manifest())
    pin = runtime.RuntimePin(
        default.repository,
        "a" * 40,
        default.lock_path,
        None,
        default.project_distribution,
        None,
        default.executable,
    )
    cache_identity = runtime.RuntimeIdentity(
        pin.repository,
        pin.revision,
        "c" * 64,
        runtime.python_token(),
        runtime.platform_token(),
    )
    target = tmp_path / cache_identity.digest()
    target.mkdir(parents=True)
    write_fake_runtime_entrypoints(target, pin.executable)
    runtime.marker_path(target).write_text(
        json.dumps(runtime.expected_marker(cache_identity, pin, "9.9.9")),
        encoding="utf-8",
    )
    assert runtime.ensure_runtime(pin, root=tmp_path) == target


def test_runtime_environment_removes_external_python_and_pip_inputs() -> None:
    env = runtime.sanitized_environment(
        {
            "PATH": "keep",
            "PIP_INDEX_URL": "https://example.invalid",
            "PYTHONPATH": "host-path",
            "OTHER": "keep-too",
        }
    )
    assert env["PATH"] == "keep"
    assert env["OTHER"] == "keep-too"
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PIP_CONFIG_FILE"] == os.devnull
    assert "PIP_INDEX_URL" not in env
    assert "PYTHONPATH" not in env


def test_cached_runner_places_global_repository_option_before_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    cached_python = tmp_path / "runtime" / "venv" / "python"
    command_prefix = [str(cached_python), "-I", "-m", "agent_policy.cli"]
    observed: dict[str, object] = {}

    monkeypatch.setattr(runner, "find_repository_root", lambda _value: repository)
    monkeypatch.setattr(runner, "runtime_command", lambda _value: command_prefix)
    monkeypatch.setattr(
        runner,
        "sanitized_environment",
        lambda: {"PATH": os.environ.get("PATH", "")},
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["cwd"] = kwargs["cwd"]
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run.py", "--repository", str(repository), "validate"],
    )

    assert runner.main() == 0
    assert observed["command"] == [
        *command_prefix,
        "--repository",
        str(repository),
        "validate",
    ]
    assert observed["cwd"] == repository


@pytest.mark.parametrize(
    ("state", "strategy"),
    [("unmanaged-empty", "fresh"), ("unmanaged-existing", "migration")],
)
def test_bootstrap_selects_state_derived_adoption_strategy(
    state: str,
    strategy: str,
) -> None:
    assert bootstrap.adoption_strategy(state) == strategy


@pytest.mark.parametrize("state", ["managed", "inconsistent", "unknown"])
def test_bootstrap_refuses_non_onboarding_states(state: str) -> None:
    with pytest.raises(ValueError):
        bootstrap.adoption_strategy(state)


def test_migration_bootstrap_never_exposes_finalize(tmp_path: Path) -> None:
    manifest = bootstrap.validated_manifest()
    arguments = bootstrap.action_arguments(
        manifest,
        tmp_path,
        "migration",
        stable_toolchain()["revision"],
        apply=True,
        primary_instructions="AGENTS.md",
    )
    assert ["adopt", "prepare"] == arguments[2:4]
    assert "finalize" not in arguments
    assert bootstrap.post_apply_arguments(manifest, tmp_path, "migration") == [
        ["--repository", str(tmp_path), "adopt", "preview"]
    ]


def write_skill_marker(directory: Path, name: str = "agent-policy") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\n---\n\nBody.\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("module", [installer, uninstaller])
def test_destructive_guards_require_agent_policy_front_matter(
    module: ModuleType,
    tmp_path: Path,
) -> None:
    target = tmp_path / "different"
    write_skill_marker(target, "different-skill")
    assert module.read_front_matter_name(target / "SKILL.md") == "different-skill"
    assert not module.is_agent_policy_skill_directory(target)


def test_installer_replacement_is_staged_atomically(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    write_skill_marker(source)
    (source / "new.txt").write_text("new", encoding="utf-8")
    target = tmp_path / "installed"
    write_skill_marker(target)
    (target / "old.txt").write_text("old", encoding="utf-8")
    monkeypatch.setattr(installer, "skill_root", lambda: source)
    monkeypatch.setattr(sys, "argv", ["install.py", str(target), "--replace"])

    assert installer.main() == 0
    assert (target / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (target / "old.txt").exists()

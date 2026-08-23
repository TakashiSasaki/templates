from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "skills/agent-policy/scripts/runtime.py"
BOOTSTRAP_PATH = ROOT / "skills/agent-policy/scripts/bootstrap.py"
SCRIPTS = RUNTIME_PATH.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_script("agent_policy_runtime_relocation_runtime", RUNTIME_PATH)
bootstrap = load_script("agent_policy_runtime_relocation_bootstrap", BOOTSTRAP_PATH)


def pin() -> Any:
    return runtime.RuntimePin(
        repository="TakashiSasaki/templates",
        revision="a" * 40,
        lock_path="requirements-runtime.lock",
        expected_lock_sha256=None,
        project_distribution="takashisasaki-agent-policy",
        project_version="0.1.0",
        executable="agent-policy",
    )


def identity() -> Any:
    return runtime.RuntimeIdentity(
        repository="TakashiSasaki/templates",
        revision="a" * 40,
        lock_sha256="b" * 64,
        python=runtime.python_token(),
        platform=runtime.platform_token(),
    )


def fake_runtime_builder(
    monkeypatch: pytest.MonkeyPatch,
    target: Path,
    runtime_pin: Any,
    *,
    fail_smoke: bool = False,
) -> list[list[str]]:
    commands: list[list[str]] = []

    def fake_run(command: list[str], *, env: object) -> None:
        commands.append(command)
        if command[1:4] == ["-I", "-m", "venv"]:
            stage = Path(command[-1]).parent
            cached_python = runtime.venv_python(stage)
            cached_python.parent.mkdir(parents=True, exist_ok=True)
            cached_python.write_text("python", encoding="utf-8")
            console = runtime.executable_path(stage, runtime_pin.executable)
            console.parent.mkdir(parents=True, exist_ok=True)
            console.write_text("console", encoding="utf-8")
        if command == [*runtime.cli_command(target), "--help"] and fail_smoke:
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(runtime, "run", fake_run)
    monkeypatch.setattr(runtime, "verify_installed_set", lambda *args: "0.1.0")
    return commands


def test_build_runtime_smokes_module_entrypoint_after_final_rename(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_pin = pin()
    runtime_identity = identity()
    target = tmp_path / "cache" / runtime_identity.digest()
    commands = fake_runtime_builder(monkeypatch, target, runtime_pin)

    result = runtime.build_runtime(
        target,
        runtime_identity,
        runtime_pin,
        b"Jinja2===3.1.6\n",
    )

    assert result == target
    assert target.is_dir()
    assert commands[-1] == [*runtime.cli_command(target), "--help"]
    assert str(target) in commands[-1][0]
    assert not any(
        path.name.startswith(f".{target.name}.build-")
        for path in target.parent.iterdir()
    )


def test_build_runtime_restores_previous_cache_when_post_rename_smoke_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_pin = pin()
    runtime_identity = identity()
    target = tmp_path / "cache" / runtime_identity.digest()
    target.mkdir(parents=True)
    (target / "previous-runtime.txt").write_text("preserve", encoding="utf-8")
    fake_runtime_builder(monkeypatch, target, runtime_pin, fail_smoke=True)

    with pytest.raises(subprocess.CalledProcessError):
        runtime.build_runtime(
            target,
            runtime_identity,
            runtime_pin,
            b"Jinja2===3.1.6\n",
        )

    assert (target / "previous-runtime.txt").read_text(encoding="utf-8") == "preserve"
    assert not runtime.marker_path(target).exists()
    assert not any(
        path.name.startswith(f".{target.name}.backup-")
        for path in target.parent.iterdir()
    )
    assert not any(
        path.name.startswith(f".{target.name}.build-")
        for path in target.parent.iterdir()
    )


def test_bootstrap_toolchain_preserves_module_entrypoint_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    prefix = ["cached-python", "-I", "-m", "agent_policy.cli"]
    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["cwd"] = kwargs["cwd"]
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    toolchain = bootstrap.Toolchain(prefix, tmp_path)
    result = toolchain.run(["--repository", str(tmp_path), "validate"])

    assert result.returncode == 0
    assert observed["command"] == [
        *prefix,
        "--repository",
        str(tmp_path),
        "validate",
    ]
    assert observed["cwd"] == tmp_path

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skills/agent-policy/scripts"
SRC = ROOT / "src"


def load_script(name: str, path: Path) -> ModuleType:
    sys.path.insert(0, str(SKILL_SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SKILL_SCRIPTS))


review_base = load_script(
    "trusted_review_base_test",
    SKILL_SCRIPTS / "review_base.py",
)
runtime_image = load_script(
    "trusted_runtime_image_test",
    SKILL_SCRIPTS / "runtime_image.py",
)


def test_review_base_git_environment_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    injected = {
        "GIT_DIR": "/attacker/repository",
        "GIT_OBJECT_DIRECTORY": "/attacker/objects",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/attacker/alternate",
        "GIT_CONFIG_PARAMETERS": "'core.fsmonitor'='attacker'",
        "GIT_CONFIG_KEY_0": "core.fsmonitor",
        "GIT_CONFIG_VALUE_0": "attacker",
        "HOME": "/attacker/home",
    }
    for name, value in injected.items():
        monkeypatch.setenv(name, value)

    environment = review_base.git_environment()

    for name in injected:
        assert name not in environment
    assert environment["GIT_CONFIG_COUNT"] == "0"
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["GIT_NO_REPLACE_OBJECTS"] == "1"


def test_review_base_command_disables_replace_objects(tmp_path: Path) -> None:
    command = review_base.git_command(
        tmp_path / "git",
        tmp_path / "repository",
        ["rev-parse", "HEAD"],
    )
    assert command[1] == "--no-replace-objects"


def pin() -> object:
    return runtime_image.RuntimePin(
        repository="TakashiSasaki/templates",
        revision="a" * 40,
        lock_path="requirements-runtime.lock",
        expected_lock_sha256="b" * 64,
        project_distribution="agent-policy",
        project_version="1.0",
        executable="agent-policy",
    )


def attestation(runtime_pin: object) -> dict[str, object]:
    return {
        "schema_version": 1,
        "runtime": {
            "repository": runtime_pin.repository,
            "revision": runtime_pin.revision,
            "lock_sha256": runtime_pin.expected_lock_sha256,
            "python": runtime_image.python_token(),
            "platform": runtime_image.platform_token(),
        },
        "selected_pin": {
            "repository": runtime_pin.repository,
            "revision": runtime_pin.revision,
        },
        "distributions": {"agent-policy": "1.0"},
        "entries": {
            "runtime.json": {
                "type": "file",
                "mode": "644",
                "sha256": "c" * 64,
            }
        },
    }


def test_runtime_attestation_rejects_runtime_identity_drift() -> None:
    runtime_pin = pin()
    value = attestation(runtime_pin)
    value["runtime"]["revision"] = "d" * 40

    with pytest.raises(ValueError, match="identity does not match"):
        runtime_image._attestation_for_pin(value, runtime_pin)


def test_runtime_attestation_rejects_lock_digest_drift() -> None:
    runtime_pin = pin()
    value = attestation(runtime_pin)
    value["runtime"]["lock_sha256"] = "d" * 64

    with pytest.raises(ValueError, match="lock digest"):
        runtime_image._attestation_for_pin(value, runtime_pin)


def test_runtime_attestation_must_be_external_to_snapshot(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "snapshot"
    repository.mkdir()
    path = repository / "runtime-attestation.json"
    path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="outside the trusted-base snapshot"):
        runtime_image._load_attestation(repository, path)


def test_runtime_attestation_shape_is_closed(tmp_path: Path) -> None:
    repository = tmp_path / "snapshot"
    repository.mkdir()
    trust = tmp_path / "trust"
    trust.mkdir()
    path = trust / "runtime-attestation.json"
    runtime_pin = pin()
    value = attestation(runtime_pin)
    value["unexpected"] = True
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="shape is invalid"):
        runtime_image._load_attestation(repository, path)


def _write_path_dependent_runtime(root: Path, build_path: str) -> None:
    root.mkdir()
    (root / "runtime.json").write_text('{"runtime":"stable"}\n', encoding="utf-8")
    (root / "requirements-runtime.lock").write_text("demo===1.0\n", encoding="utf-8")

    venv = root / "venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text(
        "home = /trusted/python\n"
        "include-system-site-packages = false\n"
        "version = 3.12.13\n"
        "executable = /trusted/python/python\n"
        f"command = /trusted/python/python -m venv {build_path}/venv\n",
        encoding="utf-8",
    )

    scripts = venv / ("Scripts" if runtime_image.os.name == "nt" else "bin")
    scripts.mkdir()
    python_name = "python.exe" if runtime_image.os.name == "nt" else "python"
    python = scripts / python_name
    python.write_bytes(b"stable-python-binary\n")
    python.chmod(0o755)
    launcher_name = "agent-policy.exe" if runtime_image.os.name == "nt" else "agent-policy"
    launcher = scripts / launcher_name
    launcher.write_text(f"#!{build_path}/venv/{python_name}\n", encoding="utf-8")
    launcher.chmod(0o755)

    site_packages = venv / "lib" / "site-packages"
    site_packages.mkdir(parents=True)
    (site_packages / "demo.py").write_text("VALUE = 1\n", encoding="utf-8")
    dist_info = site_packages / "demo-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text("Name: demo\nVersion: 1.0\n", encoding="utf-8")
    (dist_info / "RECORD").write_text(
        f"../../../bin/agent-policy,sha256={build_path},1\n",
        encoding="utf-8",
    )


def test_runtime_normalization_removes_build_path_dependent_bytes(tmp_path: Path) -> None:
    first = tmp_path / "first-runtime"
    second = tmp_path / "second-runtime"
    _write_path_dependent_runtime(first, "/tmp/first-random-build")
    _write_path_dependent_runtime(second, "/tmp/second-random-build")

    first_image = tmp_path / "first-image"
    second_image = tmp_path / "second-image"
    first_image.mkdir()
    second_image.mkdir()
    runtime_image._copy_normalized_runtime(first, first_image)
    runtime_image._copy_normalized_runtime(second, second_image)

    assert runtime_image.image_inventory(first_image) == runtime_image.image_inventory(second_image)
    config = (first_image / "venv" / "pyvenv.cfg").read_text(encoding="utf-8")
    assert runtime_image.NORMALIZED_VENV_COMMAND in config
    assert "first-random-build" not in config

    scripts = first_image / "venv" / (
        "Scripts" if runtime_image.os.name == "nt" else "bin"
    )
    launcher_name = "agent-policy.exe" if runtime_image.os.name == "nt" else "agent-policy"
    assert not (scripts / launcher_name).exists()
    assert not any(first_image.rglob("RECORD"))


def test_runtime_execution_is_bytecode_free_and_postchecked() -> None:
    runtime_source = (SKILL_SCRIPTS / "runtime_image.py").read_text(
        encoding="utf-8"
    )
    run_source = (SKILL_SCRIPTS / "run.py").read_text(encoding="utf-8")

    pip_check = '[str(python), "-B", "-I", "-m", "pip", "check"]'
    managed_cli = '"-B", "-I", "-m", CLI_MODULE'
    assert pip_check in runtime_source
    assert runtime_source.count("image_inventory(target)") >= 2
    assert managed_cli in run_source
    assert "Execution must not mutate the frozen runtime image" in run_source


def test_trusted_snapshot_cli_rejects_mutating_commands(tmp_path: Path) -> None:
    sys.path.insert(0, str(SRC))
    try:
        from agent_policy import cli
    finally:
        sys.path.remove(str(SRC))

    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    status = cli.main(
        [
            "--repository",
            str(snapshot),
            "--trusted-review-snapshot",
            "render",
        ]
    )
    assert status == 2


def test_trusted_snapshot_path_rejects_symlink_component(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(SRC))
    try:
        from agent_policy.paths import find_trusted_snapshot_root
    finally:
        sys.path.remove(str(SRC))

    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available on this platform")

    with pytest.raises(ValueError, match="symbolic-link component"):
        find_trusted_snapshot_root(alias)

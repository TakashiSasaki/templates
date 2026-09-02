from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skills/agent-policy/scripts"
SRC = ROOT / "src"
INSTALLER = ROOT / "scripts/install_agent_policy_skill.py"


def load_script(name: str, path: Path, *, search_path: Path | None = None) -> ModuleType:
    if search_path is not None:
        sys.path.insert(0, str(search_path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if search_path is not None:
            sys.path.remove(str(search_path))


runtime_image = load_script(
    "trusted_runtime_image_hardening_test",
    SKILL_SCRIPTS / "runtime_image.py",
    search_path=SKILL_SCRIPTS,
)
trusted_run = load_script(
    "trusted_run_hardening_test",
    SKILL_SCRIPTS / "run.py",
    search_path=SKILL_SCRIPTS,
)
installer = load_script(
    "trusted_installer_hardening_test",
    INSTALLER,
)


def test_trusted_arguments_reject_wrapper_option_overrides() -> None:
    assert trusted_run._trusted_arguments(["check"]) == ["check"]
    assert trusted_run._trusted_arguments(["validate", "--config", "policy.yml"]) == [
        "validate",
        "--config",
        "policy.yml",
    ]

    rejected = [
        ["--repository", "/attacker", "check"],
        ["check", "--repository", "/attacker"],
        ["check", "--repository=/attacker"],
        ["--format=json", "check"],
        ["check", "--trusted-review-snapshot"],
        ["render"],
    ]
    for arguments in rejected:
        with pytest.raises(ValueError):
            trusted_run._trusted_arguments(arguments)


def test_trusted_environment_drops_loader_and_general_process_overrides() -> None:
    environment = runtime_image.trusted_environment(
        {
            "LD_PRELOAD": "/attacker/preload.so",
            "LD_LIBRARY_PATH": "/attacker/lib",
            "DYLD_INSERT_LIBRARIES": "/attacker/lib.dylib",
            "PATH": "/attacker/bin",
            "HOME": "/attacker/home",
            "PYTHONPATH": "/attacker/python",
            "PIP_INDEX_URL": "https://attacker.invalid/simple",
            "UNRELATED": "attacker",
            "TMPDIR": "/trusted/tmp",
        }
    )

    for name in (
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        "PATH",
        "HOME",
        "PYTHONPATH",
        "PIP_INDEX_URL",
        "UNRELATED",
    ):
        assert name not in environment
    assert environment["TMPDIR"] == "/trusted/tmp"
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["PIP_CONFIG_FILE"] == os.devnull
    assert environment["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"
    assert environment["LC_ALL"] == "C"
    assert environment["LANG"] == "C"


def test_runtime_normalization_rejects_external_file_symlink(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "runtime.json").write_text("{}\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 'attacker'\n", encoding="utf-8")
    link = runtime / "payload.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are not available on this platform")

    with pytest.raises(ValueError, match="file symlink outside its root"):
        runtime_image._walk_normalized_sources(runtime)


def test_runtime_normalization_allows_only_trusted_external_python_launcher(
    tmp_path: Path,
) -> None:
    if os.name == "nt":
        pytest.skip("Windows virtual environments use copied Python launchers")
    runtime = tmp_path / "runtime"
    bin_dir = runtime / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    (runtime / "runtime.json").write_text("{}\n", encoding="utf-8")
    launcher = bin_dir / "python"
    try:
        launcher.symlink_to(Path(sys.executable).resolve())
    except OSError:
        pytest.skip("symlinks are not available on this platform")

    sources = runtime_image._walk_normalized_sources(runtime)
    by_path = {relative: source for relative, source, _mode in sources}
    assert by_path["venv/bin/python"] == Path(sys.executable).resolve()


def test_installer_attestation_preflight_rejects_reverse_overlap(tmp_path: Path) -> None:
    attestation = tmp_path / "trust" / "attestation.json"
    target = attestation / "agent-policy"

    with pytest.raises(ValueError, match="overlap"):
        installer.preflight_attestation_destination(target, attestation)
    assert not attestation.exists()


def test_installer_attestation_creation_never_clobbers_existing_path(
    tmp_path: Path,
) -> None:
    target = tmp_path / "agent-policy"
    scripts = target / "scripts"
    scripts.mkdir(parents=True)
    (target / "SKILL.md").write_text("---\nname: agent-policy\n---\n", encoding="utf-8")
    (target / "runtime-manifest.json").write_text("{}\n", encoding="utf-8")
    (scripts / "install.py").write_text("pass\n", encoding="utf-8")

    attestation = tmp_path / "trust" / "attestation.json"
    attestation.parent.mkdir()
    attestation.write_text("protected-existing-evidence\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must not already exist"):
        installer.write_installation_attestation(
            target,
            attestation,
            installer_revision="a" * 40,
        )
    assert attestation.read_text(encoding="utf-8") == "protected-existing-evidence\n"


def test_check_staging_can_restore_owner_writability(tmp_path: Path) -> None:
    sys.path.insert(0, str(SRC))
    try:
        from agent_policy.commands import check as check_command
    finally:
        sys.path.remove(str(SRC))

    root = tmp_path / "staged"
    child = root / "nested"
    child.mkdir(parents=True)
    file = child / "generated.txt"
    file.write_text("content\n", encoding="utf-8")
    file.chmod(0o444)
    child.chmod(0o555)
    root.chmod(0o555)

    check_command._make_staging_writable(root)

    assert root.stat().st_mode & stat.S_IWUSR
    assert child.stat().st_mode & stat.S_IWUSR
    assert file.stat().st_mode & stat.S_IWUSR

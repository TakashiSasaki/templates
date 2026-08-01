from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/bootstrap-agent-policy"


def load_script(name: str, relative: str) -> ModuleType:
    module_path = SKILL_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


installer = load_script(
    "bootstrap_agent_policy_installation_safety",
    "scripts/install.py",
)
uninstaller = load_script(
    "bootstrap_agent_policy_uninstallation_safety",
    "scripts/uninstall.py",
)


def write_bootstrap_skill(directory: Path, extra_name: str | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        """---
name: bootstrap-agent-policy
---

Body.
""",
        encoding="utf-8",
    )
    if extra_name is not None:
        (directory / extra_name).write_text(extra_name, encoding="utf-8")


@pytest.mark.parametrize("module", [installer, uninstaller])
def test_destructive_commands_reject_symlinked_identity_markers(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    canonical = tmp_path / "canonical"
    write_bootstrap_skill(canonical)
    target = tmp_path / "unrelated"
    target.mkdir()
    sentinel = target / "unrelated.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    marker = target / "SKILL.md"
    marker.symlink_to(canonical / "SKILL.md")

    arguments = ["install.py", str(target), "--replace"]
    if module is uninstaller:
        arguments = ["uninstall.py", str(target)]
    monkeypatch.setattr(sys, "argv", arguments)

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 2
    assert target.is_dir()
    assert marker.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert (canonical / "SKILL.md").is_file()


def test_replacement_copy_failure_preserves_existing_installation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    write_bootstrap_skill(source, "new.txt")
    target = tmp_path / "installed"
    write_bootstrap_skill(target, "old.txt")
    monkeypatch.setattr(installer, "skill_root", lambda: source)

    def fail_copy(*args: object, **kwargs: object) -> None:
        raise OSError("simulated copy failure")

    monkeypatch.setattr(installer.shutil, "copytree", fail_copy)
    monkeypatch.setattr(sys, "argv", ["install.py", str(target), "--replace"])

    with pytest.raises(OSError, match="simulated copy failure"):
        installer.main()

    assert (target / "SKILL.md").is_file()
    assert (target / "old.txt").read_text(encoding="utf-8") == "old.txt"
    assert not (target / "new.txt").exists()
    assert list(tmp_path.glob(".installed.install-*")) == []


def test_replacement_switch_failure_restores_existing_installation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    write_bootstrap_skill(source, "new.txt")
    target = tmp_path / "installed"
    write_bootstrap_skill(target, "old.txt")
    monkeypatch.setattr(installer, "skill_root", lambda: source)
    original_rename = Path.rename

    def fail_staged_switch(path: Path, destination: Path) -> Path:
        if path.name == "staged":
            raise OSError("simulated switch failure")
        return original_rename(path, destination)

    monkeypatch.setattr(Path, "rename", fail_staged_switch)
    monkeypatch.setattr(sys, "argv", ["install.py", str(target), "--replace"])

    with pytest.raises(OSError, match="simulated switch failure"):
        installer.main()

    assert (target / "SKILL.md").is_file()
    assert (target / "old.txt").read_text(encoding="utf-8") == "old.txt"
    assert not (target / "new.txt").exists()
    assert list(tmp_path.glob(".installed.install-*")) == []


def test_successful_replacement_activates_complete_staged_copy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    write_bootstrap_skill(source, "new.txt")
    target = tmp_path / "installed"
    write_bootstrap_skill(target, "old.txt")
    monkeypatch.setattr(installer, "skill_root", lambda: source)
    monkeypatch.setattr(sys, "argv", ["install.py", str(target), "--replace"])

    assert installer.main() == 0

    assert (target / "SKILL.md").is_file()
    assert (target / "new.txt").read_text(encoding="utf-8") == "new.txt"
    assert not (target / "old.txt").exists()
    assert list(tmp_path.glob(".installed.install-*")) == []

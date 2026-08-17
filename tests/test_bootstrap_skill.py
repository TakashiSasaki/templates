from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/bootstrap-agent-policy"


def stable_toolchain() -> dict[str, str]:
    release = json.loads((ROOT / "release/toolchain.json").read_text(encoding="utf-8"))
    toolchain = release["toolchain"]
    assert isinstance(toolchain, dict)
    return toolchain


def load_script(name: str, relative: str) -> ModuleType:
    module_path = SKILL_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bootstrap = load_script("bootstrap_agent_policy", "scripts/bootstrap.py")
installer = load_script("bootstrap_agent_policy_install", "scripts/install.py")
uninstaller = load_script("bootstrap_agent_policy_uninstall", "scripts/uninstall.py")


def test_manifest_pins_reviewed_templates_policy_sha() -> None:
    manifest = bootstrap.load_manifest()
    toolchain = stable_toolchain()
    assert manifest["toolchain"] == toolchain
    revision = toolchain["revision"]
    assert bootstrap.FULL_SHA.fullmatch(revision)


def test_requirement_is_immutable() -> None:
    value = bootstrap.git_requirement("TakashiSasaki/templates", "a" * 40)
    assert value == "git+https://github.com/TakashiSasaki/templates.git@" + "a" * 40
    assert "@policy" not in value
    assert "@main" not in value


def test_manifest_declares_adoption_strategies_without_finalization() -> None:
    manifest = bootstrap.load_manifest()
    assert manifest["schema_version"] == 2
    assert manifest["routes"] == bootstrap.EXPECTED_ROUTES
    assert "init" not in manifest["routes"]
    assert manifest["routes"]["fresh_prepare"] == ["init"]
    assert "finalize" not in json.dumps(manifest["routes"])


def test_skill_instructions_preserve_trust_boundary() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "name: bootstrap-agent-policy" in skill
    assert "full commit SHA" in skill
    assert "must never invoke adoption finalization" in skill
    assert "Do not commit, push, create branches" in skill
    assert "Do not require the user to choose between initialization and adoption routes" in skill


def test_parse_inspection_reads_state_and_sources() -> None:
    inspection = bootstrap.parse_inspection(
        json.dumps(
            [
                {"level": "info", "code": "ADOPTION_STATE", "message": "unmanaged-existing", "path": None},
                {"level": "info", "code": "ADOPTION_SOURCE", "message": "sha256=x; generated=false", "path": "CLAUDE.md"},
                {"level": "info", "code": "ADOPTION_SOURCE", "message": "sha256=y; generated=false", "path": "AGENTS.md"},
            ]
        )
    )
    assert inspection == bootstrap.Inspection(
        state="unmanaged-existing",
        sources=("AGENTS.md", "CLAUDE.md"),
    )


@pytest.mark.parametrize(
    ("state", "strategy"),
    [
        ("unmanaged-empty", "fresh"),
        ("unmanaged-existing", "migration"),
    ],
)
def test_repository_state_selects_adoption_strategy(state: str, strategy: str) -> None:
    assert bootstrap.adoption_strategy(state) == strategy


@pytest.mark.parametrize("state", ["managed", "inconsistent", "unknown"])
def test_refusal_states_do_not_select_an_adoption_strategy(state: str) -> None:
    with pytest.raises(ValueError):
        bootstrap.adoption_strategy(state)


def test_bootstrap_cli_has_no_route_option() -> None:
    args = bootstrap.parse_args([])
    assert not hasattr(args, "route")
    with pytest.raises(SystemExit):
        bootstrap.parse_args(["--route", "init"])


def test_primary_instructions_option_is_unset_by_default() -> None:
    assert bootstrap.parse_args([]).primary_instructions is None


def test_fresh_adoption_has_no_primary_instructions() -> None:
    inspection = bootstrap.Inspection("unmanaged-empty", ())
    assert bootstrap.select_primary_instructions(inspection, None, apply=True) is None
    with pytest.raises(ValueError, match="Fresh adoption has no existing primary instructions"):
        bootstrap.select_primary_instructions(inspection, "AGENTS.md", apply=False)


@pytest.mark.parametrize(
    "relative",
    ["CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md"],
)
def test_migration_adoption_auto_selects_only_supported_instruction(relative: str) -> None:
    inspection = bootstrap.Inspection("unmanaged-existing", (relative,))
    assert bootstrap.select_primary_instructions(inspection, None, apply=False) == relative


def test_ambiguous_migration_dry_run_stops_without_guessing() -> None:
    inspection = bootstrap.Inspection("unmanaged-existing", ("AGENTS.md", "CLAUDE.md"))
    assert bootstrap.select_primary_instructions(inspection, None, apply=False) is None
    with pytest.raises(ValueError, match="requires --primary-instructions"):
        bootstrap.select_primary_instructions(inspection, None, apply=True)


def test_migration_requires_discovered_primary_instructions() -> None:
    inspection = bootstrap.Inspection("unmanaged-existing", ("CLAUDE.md",))
    with pytest.raises(ValueError, match="available: CLAUDE.md"):
        bootstrap.select_primary_instructions(inspection, "AGENTS.md", apply=False)
    assert bootstrap.select_primary_instructions(inspection, "CLAUDE.md", apply=False) == "CLAUDE.md"


def test_fresh_apply_uses_internal_init_primitive(tmp_path: Path) -> None:
    manifest = bootstrap.load_manifest()
    arguments = bootstrap.action_arguments(
        manifest,
        tmp_path,
        "fresh",
        "a" * 40,
        apply=True,
        primary_instructions=None,
    )
    assert arguments[-1] == "--apply"
    assert arguments[2] == "init"
    assert "adopt" not in arguments
    assert "finalize" not in arguments


def test_migration_apply_stops_at_prepare_and_previews_afterward(tmp_path: Path) -> None:
    manifest = bootstrap.load_manifest()
    arguments = bootstrap.action_arguments(
        manifest,
        tmp_path,
        "migration",
        "a" * 40,
        apply=True,
        primary_instructions="CLAUDE.md",
    )
    assert arguments[-1] == "--apply"
    assert ["adopt", "prepare"] == arguments[2:4]
    assert arguments[-3:-1] == ["--primary-instructions", "CLAUDE.md"]
    assert "finalize" not in arguments
    assert bootstrap.post_apply_arguments(manifest, tmp_path, "migration") == [
        ["--repository", str(tmp_path), "adopt", "preview"]
    ]


def test_fresh_post_apply_validates_and_checks(tmp_path: Path) -> None:
    manifest = bootstrap.load_manifest()
    assert bootstrap.post_apply_arguments(manifest, tmp_path, "fresh") == [
        ["--repository", str(tmp_path), "validate"],
        ["--repository", str(tmp_path), "check"],
    ]


@pytest.mark.parametrize("module", [installer, uninstaller])
def test_destructive_guards_require_actual_front_matter_name(
    module: ModuleType,
    tmp_path: Path,
) -> None:
    target = tmp_path / "different-skill"
    target.mkdir()
    (target / "SKILL.md").write_text(
        """---
name: different-skill
---

The body mentions name: bootstrap-agent-policy but is not that skill.
""",
        encoding="utf-8",
    )
    assert module.read_front_matter_name(target / "SKILL.md") == "different-skill"
    assert not module.is_bootstrap_skill_directory(target)


@pytest.mark.parametrize("module", [installer, uninstaller])
def test_destructive_guards_accept_exact_quoted_front_matter_name(
    module: ModuleType,
    tmp_path: Path,
) -> None:
    target = tmp_path / "bootstrap-agent-policy"
    target.mkdir()
    (target / "SKILL.md").write_text(
        """---
name: "bootstrap-agent-policy"
---

Body.
""",
        encoding="utf-8",
    )
    assert module.is_bootstrap_skill_directory(target)


def write_bootstrap_marker(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        """---
name: bootstrap-agent-policy
---

Body.
""",
        encoding="utf-8",
    )


@pytest.mark.parametrize("relation", ["same", "ancestor", "descendant"])
def test_installer_rejects_source_target_overlap(
    relation: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if relation == "same":
        source = tmp_path / "skill"
        target = source
        write_bootstrap_marker(source)
    elif relation == "ancestor":
        target = tmp_path / "skill-container"
        source = target / "source-skill"
        write_bootstrap_marker(target)
        write_bootstrap_marker(source)
    else:
        source = tmp_path / "source-skill"
        target = source / "nested-target"
        write_bootstrap_marker(source)

    monkeypatch.setattr(installer, "skill_root", lambda: source)
    monkeypatch.setattr(sys, "argv", ["install.py", str(target), "--replace"])

    with pytest.raises(SystemExit) as exc_info:
        installer.main()

    assert exc_info.value.code == 2
    assert source.is_dir()
    assert (source / "SKILL.md").is_file()
    if relation == "ancestor":
        assert target.is_dir()
    if relation == "descendant":
        assert not target.exists()


@pytest.mark.parametrize("module", [installer, uninstaller])
def test_destructive_commands_reject_symlink_targets(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    referent = tmp_path / "shared-skill"
    write_bootstrap_marker(referent)
    target = tmp_path / "skill-link"
    target.symlink_to(referent, target_is_directory=True)
    arguments = ["install.py", str(target), "--replace"]
    if module is uninstaller:
        arguments = ["uninstall.py", str(target)]
    monkeypatch.setattr(sys, "argv", arguments)

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 2
    assert target.is_symlink()
    assert referent.is_dir()
    assert (referent / "SKILL.md").is_file()

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


bootstrap = load_script(
    "bootstrap_agent_policy",
    "scripts/bootstrap.py",
)
installer = load_script(
    "bootstrap_agent_policy_install",
    "scripts/install.py",
)
uninstaller = load_script(
    "bootstrap_agent_policy_uninstall",
    "scripts/uninstall.py",
)


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


def test_manifest_declares_only_non_finalizing_routes() -> None:
    manifest = bootstrap.load_manifest()
    assert manifest["schema_version"] == 2
    assert manifest["routes"] == bootstrap.EXPECTED_ROUTES
    assert "finalize" not in json.dumps(manifest["routes"])


def test_skill_instructions_preserve_trust_boundary() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "name: bootstrap-agent-policy" in skill
    assert "full commit SHA" in skill
    assert "must never invoke adoption finalization" in skill
    assert "Do not commit, push, create branches" in skill
    assert "TakashiSasaki/agent-policy" not in skill


def test_parse_inspection_reads_state_and_sources() -> None:
    inspection = bootstrap.parse_inspection(
        json.dumps(
            [
                {
                    "level": "info",
                    "code": "ADOPTION_STATE",
                    "message": "unmanaged-existing",
                    "path": None,
                },
                {
                    "level": "info",
                    "code": "ADOPTION_SOURCE",
                    "message": "sha256=x; generated=false",
                    "path": "CLAUDE.md",
                },
                {
                    "level": "info",
                    "code": "ADOPTION_SOURCE",
                    "message": "sha256=y; generated=false",
                    "path": "AGENTS.md",
                },
            ]
        )
    )
    assert inspection == bootstrap.Inspection(
        state="unmanaged-existing",
        sources=("AGENTS.md", "CLAUDE.md"),
    )


@pytest.mark.parametrize(
    ("state", "route"),
    [
        ("unmanaged-empty", "init"),
        ("unmanaged-existing", "adopt"),
    ],
)
def test_dry_run_auto_selects_advisory_route(state: str, route: str) -> None:
    assert bootstrap.select_route(state, "auto", apply=False) == route


def test_apply_requires_explicit_route() -> None:
    with pytest.raises(ValueError, match="explicit --route"):
        bootstrap.select_route("unmanaged-empty", "auto", apply=True)


@pytest.mark.parametrize("state", ["managed", "inconsistent", "unknown"])
def test_refusal_states_do_not_select_a_route(state: str) -> None:
    with pytest.raises(ValueError):
        bootstrap.select_route(state, "auto", apply=False)


def test_explicit_route_must_match_inspection() -> None:
    with pytest.raises(ValueError, match="recommended route is adopt"):
        bootstrap.select_route("unmanaged-existing", "init", apply=False)


def test_primary_instructions_option_is_unset_by_default() -> None:
    assert bootstrap.parse_args([]).primary_instructions is None


@pytest.mark.parametrize(
    "relative",
    ["CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md"],
)
def test_adoption_auto_selects_only_supported_instruction(relative: str) -> None:
    inspection = bootstrap.Inspection("unmanaged-existing", (relative,))
    assert (
        bootstrap.select_primary_instructions(
            inspection,
            "adopt",
            None,
            apply=False,
        )
        == relative
    )


def test_ambiguous_adoption_dry_run_stops_without_guessing() -> None:
    inspection = bootstrap.Inspection(
        "unmanaged-existing",
        ("AGENTS.md", "CLAUDE.md"),
    )
    assert (
        bootstrap.select_primary_instructions(
            inspection,
            "adopt",
            None,
            apply=False,
        )
        is None
    )
    with pytest.raises(ValueError, match="requires --primary-instructions"):
        bootstrap.select_primary_instructions(
            inspection,
            "adopt",
            None,
            apply=True,
        )


def test_adoption_requires_discovered_primary_instructions() -> None:
    inspection = bootstrap.Inspection("unmanaged-existing", ("CLAUDE.md",))
    with pytest.raises(ValueError, match="available: CLAUDE.md"):
        bootstrap.select_primary_instructions(
            inspection,
            "adopt",
            "AGENTS.md",
            apply=False,
        )
    assert (
        bootstrap.select_primary_instructions(
            inspection,
            "adopt",
            "CLAUDE.md",
            apply=False,
        )
        == "CLAUDE.md"
    )


def test_init_apply_arguments_do_not_contain_adoption_commands(tmp_path: Path) -> None:
    manifest = bootstrap.load_manifest()
    arguments = bootstrap.action_arguments(
        manifest,
        tmp_path,
        "init",
        "a" * 40,
        apply=True,
        primary_instructions=None,
    )
    assert arguments[-1] == "--apply"
    assert "init" in arguments
    assert "adopt" not in arguments
    assert "finalize" not in arguments


def test_adopt_apply_stops_at_prepare_and_previews_afterward(tmp_path: Path) -> None:
    manifest = bootstrap.load_manifest()
    arguments = bootstrap.action_arguments(
        manifest,
        tmp_path,
        "adopt",
        "a" * 40,
        apply=True,
        primary_instructions="CLAUDE.md",
    )
    assert arguments[-1] == "--apply"
    assert ["adopt", "prepare"] == arguments[2:4]
    assert arguments[-3:-1] == ["--primary-instructions", "CLAUDE.md"]
    assert "finalize" not in arguments
    assert bootstrap.post_apply_arguments(manifest, tmp_path, "adopt") == [
        ["--repository", str(tmp_path), "adopt", "preview"]
    ]


def test_init_post_apply_validates_and_checks(tmp_path: Path) -> None:
    manifest = bootstrap.load_manifest()
    assert bootstrap.post_apply_arguments(manifest, tmp_path, "init") == [
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
    monkeypatch.setattr(
        sys,
        "argv",
        ["install.py", str(target), "--replace"],
    )

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

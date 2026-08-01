from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/bootstrap-agent-policy"
MODULE_PATH = SKILL_ROOT / "scripts/bootstrap.py"
PINNED_TOOLCHAIN_REVISION = "270645381849431b922bee87afecedc540e52ed1"
SPEC = importlib.util.spec_from_file_location("bootstrap_agent_policy", MODULE_PATH)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bootstrap
SPEC.loader.exec_module(bootstrap)


def test_manifest_pins_reviewed_templates_policy_sha() -> None:
    manifest = bootstrap.load_manifest()
    assert manifest["toolchain"] == {
        "repository": "TakashiSasaki/templates",
        "revision": PINNED_TOOLCHAIN_REVISION,
    }
    assert bootstrap.FULL_SHA.fullmatch(PINNED_TOOLCHAIN_REVISION)


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


def test_adoption_requires_discovered_primary_instructions() -> None:
    inspection = bootstrap.Inspection("unmanaged-existing", ("CLAUDE.md",))
    with pytest.raises(ValueError, match="available: CLAUDE.md"):
        bootstrap.validate_primary_instructions(inspection, "adopt", "AGENTS.md")
    bootstrap.validate_primary_instructions(inspection, "adopt", "CLAUDE.md")


def test_init_apply_arguments_do_not_contain_adoption_commands(tmp_path: Path) -> None:
    manifest = bootstrap.load_manifest()
    arguments = bootstrap.action_arguments(
        manifest,
        tmp_path,
        "init",
        "a" * 40,
        apply=True,
        primary_instructions="AGENTS.md",
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

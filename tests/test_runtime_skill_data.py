from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

from agent_policy.renderer import _portable_skill_relative_path
from scripts.verify_runtime_skill_data import (
    compare_skill_inventories,
    generated_skill_inventory,
    verify_runtime_skill_data,
)

ROOT = Path(__file__).resolve().parents[1]


def test_source_generated_skill_inventory_contains_orchestration_skill() -> None:
    inventory = generated_skill_inventory(ROOT)

    assert "orchestrate-repository-change" in inventory
    assert "SKILL.md" in inventory["orchestrate-repository-change"]
    assert "agent-policy" not in inventory
    assert "pr-merge-gate" not in inventory


def test_skill_relative_paths_are_posix_on_all_supported_hosts() -> None:
    assert _portable_skill_relative_path(
        PurePosixPath("/skill/references/api.md"),
        PurePosixPath("/skill"),
    ) == "references/api.md"
    assert _portable_skill_relative_path(
        PureWindowsPath("C:/skill/references/api.md"),
        PureWindowsPath("C:/skill"),
    ) == "references/api.md"


def test_skill_inventory_comparison_fails_closed_on_missing_and_unexpected_data() -> None:
    errors = compare_skill_inventories(
        {
            "alpha": ("SKILL.md", "references/one.md"),
            "beta": ("SKILL.md",),
        },
        {
            "alpha": ("SKILL.md", "references/two.md"),
            "gamma": ("SKILL.md",),
        },
    )

    assert errors == (
        "installed generated Skills missing from package data: beta",
        "installed package data contains unexpected generated Skills: gamma",
        "installed generated Skill alpha is missing files: references/one.md",
        "installed generated Skill alpha has unexpected files: references/two.md",
    )


def test_current_source_generated_skills_render_with_matching_inventory() -> None:
    assert verify_runtime_skill_data(ROOT) == ()


def test_runtime_smoke_executes_skill_data_verifier_in_isolated_venv() -> None:
    smoke = (ROOT / "scripts" / "smoke_test_runtime_distribution.py").read_text(
        encoding="utf-8"
    )

    assert 'VERIFY_SKILL_DATA_SCRIPT = ROOT / "scripts" / "verify_runtime_skill_data.py"' in smoke
    assert 'run([str(python), "-I", str(VERIFY_SKILL_DATA_SCRIPT)], env=env)' in smoke

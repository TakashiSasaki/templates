import os
from pathlib import Path

import pytest

from agent_policy.adoption import inspect_repository
from agent_policy.commands import adopt


@pytest.mark.parametrize(
    ("artifact_name", "referent_name"),
    [
        ("AGENTS.md", "future/AGENTS.md"),
        (".agents/policies", "future/policies"),
    ],
)
def test_dangling_known_source_symlink_is_inconsistent(
    tmp_path: Path,
    artifact_name: str,
    referent_name: str,
) -> None:
    (tmp_path / ".git").mkdir()
    artifact = tmp_path / artifact_name
    artifact.parent.mkdir(parents=True, exist_ok=True)
    referent = tmp_path / referent_name
    relative_referent = os.path.relpath(referent, artifact.parent)
    try:
        artifact.symlink_to(relative_referent)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    inspection = inspect_repository(tmp_path)

    assert inspection.state == "inconsistent"
    assert inspection.sources == ()

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        enabled_skills=[],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPTION_INCONSISTENT"
    assert artifact.is_symlink()
    assert not referent.exists()
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / ".agent-policy.lock").exists()


@pytest.mark.parametrize(
    ("artifact_name", "referent_name"),
    [
        (".agents/policies/local.md", "future/policies/local.md"),
        (".agents/skills/local/SKILL.md", "future/skills/local/SKILL.md"),
    ],
)
def test_dangling_source_tree_symlink_is_inconsistent(
    tmp_path: Path,
    artifact_name: str,
    referent_name: str,
) -> None:
    (tmp_path / ".git").mkdir()
    artifact = tmp_path / artifact_name
    artifact.parent.mkdir(parents=True, exist_ok=True)
    referent = tmp_path / referent_name
    relative_referent = os.path.relpath(referent, artifact.parent)
    try:
        artifact.symlink_to(relative_referent)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    inspection = inspect_repository(tmp_path)

    assert inspection.state == "inconsistent"
    assert inspection.sources == ()

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        enabled_skills=[],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "ADOPTION_INCONSISTENT"
    assert artifact.is_symlink()
    assert not referent.exists()
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / ".agent-policy.lock").exists()

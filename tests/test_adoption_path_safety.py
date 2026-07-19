import os
from pathlib import Path

import pytest

from agent_policy.adoption import inspect_repository
from agent_policy.commands import adopt


def test_inspect_rejects_instruction_symlink_escape(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / ".git").mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    (repository / "AGENTS.md").symlink_to(outside)

    diagnostics = adopt.inspect_run(repository, ".agent-policy.yml")

    assert diagnostics[0].code == "ADOPT_INSPECT"
    assert "escapes repository root" in diagnostics[0].message


def test_prepare_rejects_state_path_escape(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        state_path="../adoption.json",
    )

    assert diagnostics[0].code == "ADOPT_PREPARE"
    assert "escapes repository root" in diagnostics[0].message
    assert not (tmp_path.parent / "adoption.json").exists()


@pytest.mark.parametrize(
    ("artifact_name", "state_path", "referent_name"),
    [
        (
            ".agent-policy/adoption.json",
            ".agent-policy/adoption.json",
            "future/adoption.json",
        ),
        (
            ".agent-policy.lock",
            ".agent-policy/adoption.json",
            "future/agent-policy.lock",
        ),
    ],
)
def test_inspect_counts_dangling_adoption_artifacts_as_inconsistent(
    tmp_path: Path,
    artifact_name: str,
    state_path: str,
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

    inspection = inspect_repository(tmp_path, state_path=state_path)

    assert inspection.state == "inconsistent"
    assert artifact.is_symlink()
    assert not referent.exists()


def test_prepare_rejects_dangling_project_policy_scaffold_symlink(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")
    policy = tmp_path / "policy/project.md"
    policy.parent.mkdir(parents=True)
    referent = tmp_path / "future/project.md"
    relative_referent = os.path.relpath(referent, policy.parent)
    try:
        policy.symlink_to(relative_referent)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        enabled_skills=[],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "FILE_CONFLICT"
    assert "policy/project.md" in diagnostics[0].message
    assert policy.is_symlink()
    assert not referent.exists()
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / ".agent-policy.lock").exists()


@pytest.mark.parametrize(
    (
        "config_path",
        "state_path",
        "preview_output_path",
        "link_name",
        "referent_name",
    ),
    [
        (
            ".agent-policy.yml",
            ".agent-policy/adoption.json",
            ".agent-policy/preview/AGENTS.md",
            ".agent-policy.yml",
            "future/config.yml",
        ),
        (
            ".agent-policy.yml",
            ".agent-policy/adoption.json",
            ".agent-policy/preview/AGENTS.md",
            ".agent-policy/adoption.json",
            "future/adoption.json",
        ),
        (
            ".agent-policy.yml",
            ".agent-policy/adoption.json",
            ".agent-policy/preview/AGENTS.md",
            ".agent-policy/preview/AGENTS.md",
            "future/preview.md",
        ),
    ],
)
def test_prepare_rejects_dangling_management_output_symlink(
    tmp_path: Path,
    config_path: str,
    state_path: str,
    preview_output_path: str,
    link_name: str,
    referent_name: str,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")
    link = tmp_path / link_name
    link.parent.mkdir(parents=True, exist_ok=True)
    referent = tmp_path / referent_name
    relative_referent = os.path.relpath(referent, link.parent)
    try:
        link.symlink_to(relative_referent)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    diagnostics = adopt.prepare_run(
        tmp_path,
        config_path,
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        state_path=state_path,
        preview_output_path=preview_output_path,
        enabled_skills=[],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "FILE_CONFLICT"
    assert link_name in diagnostics[0].message
    assert link.is_symlink()
    assert not referent.exists()
    assert not (tmp_path / ".agent-policy.lock").exists()

from pathlib import Path

from agent_policy.commands import onboard
from agent_policy.commands import check, validate


def test_adopt_prepare_handles_unmanaged_empty_as_fresh_adoption(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = onboard.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
    )

    assert diagnostics
    assert all(item.level == "info" for item in diagnostics)
    assert any(item.code == "CREATE" and item.message == ".agent-policy.yml" for item in diagnostics)
    assert not (tmp_path / ".agent-policy.yml").exists()


def test_fresh_adoption_apply_reaches_managed_state(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = onboard.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
    )

    assert diagnostics == []
    assert (tmp_path / ".agent-policy.yml").is_file()
    assert (tmp_path / ".agent-policy.lock").is_file()
    assert (tmp_path / "AGENTS.md").is_file()
    assert not (tmp_path / ".agent-policy/adoption.json").exists()
    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []


def test_fresh_adoption_rejects_primary_instructions_option(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = onboard.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        primary_instructions="AGENTS.md",
    )

    assert diagnostics[0].code == "PRIMARY_INSTRUCTIONS"
    assert not (tmp_path / ".agent-policy.yml").exists()


def test_existing_repository_still_uses_migration_preparation(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")

    diagnostics = onboard.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        primary_instructions="AGENTS.md",
    )

    assert diagnostics
    assert all(item.level == "info" for item in diagnostics)
    assert any(item.code == "PRESERVE" and item.path == "AGENTS.md" for item in diagnostics)
    assert not (tmp_path / ".agent-policy.yml").exists()

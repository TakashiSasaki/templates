from pathlib import Path

from agent_policy.commands import check, onboard, validate

TEST_TOOLCHAIN_SHA = "8" * 40


def test_adopt_prepare_handles_unmanaged_empty_as_fresh_adoption(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = onboard.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision=TEST_TOOLCHAIN_SHA,
        profiles=["core", "security-baseline"],
    )

    assert diagnostics
    assert all(item.level == "info" for item in diagnostics)
    assert any(
        item.code == "CREATE" and item.message == ".agent-policy.yml"
        for item in diagnostics
    )
    assert not (tmp_path / ".agent-policy.yml").exists()


def test_fresh_adoption_apply_reaches_managed_state(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = onboard.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision=TEST_TOOLCHAIN_SHA,
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
        toolchain_revision=TEST_TOOLCHAIN_SHA,
        profiles=["core"],
        primary_instructions="AGENTS.md",
    )

    assert diagnostics[0].code == "PRIMARY_INSTRUCTIONS"
    assert not (tmp_path / ".agent-policy.yml").exists()


def test_existing_repository_auto_selects_single_migration_primary(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("handwritten\n", encoding="utf-8")

    diagnostics = onboard.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision=TEST_TOOLCHAIN_SHA,
        profiles=["core"],
    )

    assert diagnostics
    assert all(item.level == "info" for item in diagnostics)
    assert any(item.code == "PRESERVE" and item.path == "CLAUDE.md" for item in diagnostics)
    assert not (tmp_path / ".agent-policy.yml").exists()


def test_existing_repository_requires_primary_when_discovery_is_ambiguous(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("claude\n", encoding="utf-8")

    diagnostics = onboard.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision=TEST_TOOLCHAIN_SHA,
        profiles=["core"],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "PRIMARY_INSTRUCTIONS"
    assert "ambiguous" in diagnostics[0].message
    assert "AGENTS.md" in diagnostics[0].message
    assert "CLAUDE.md" in diagnostics[0].message
    assert not (tmp_path / ".agent-policy.yml").exists()


def test_existing_repository_honors_explicit_discovered_primary(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("claude\n", encoding="utf-8")

    diagnostics = onboard.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision=TEST_TOOLCHAIN_SHA,
        profiles=["core"],
        primary_instructions="CLAUDE.md",
    )

    assert diagnostics
    assert all(item.level == "info" for item in diagnostics)
    assert any(item.code == "PRESERVE" and item.path == "CLAUDE.md" for item in diagnostics)
    assert not (tmp_path / ".agent-policy.yml").exists()

from pathlib import Path

import pytest

from agent_policy.commands import check, render, validate

PROJECT_POLICY = """---
id: project.rule
severity: mandatory
overridable: true
order: 1000
---
# Rule

Body.
"""


def _write_repository(
    repository: Path,
    *,
    output_path: str = "AGENTS.md",
    output_enabled: bool = True,
) -> None:
    (repository / ".git").mkdir()
    (repository / "policy").mkdir()
    (repository / "policy/project.md").write_text(PROJECT_POLICY, encoding="utf-8")
    enabled = "true" if output_enabled else "false"
    (repository / ".agent-policy.yml").write_text(
        f"""schema_version: 1
toolchain:
  repository: TakashiSasaki/agent-policy
  revision: LOCAL-DEVELOPMENT
profiles:
  - core
project_policy:
  files:
    - policy/project.md
outputs:
  agents:
    enabled: {enabled}
    path: {output_path}
skills:
  enabled:
    - validate-agent-policy
""",
        encoding="utf-8",
    )


def _diagnostic_pairs(repository: Path) -> set[tuple[str, str | None]]:
    return {(item.code, item.path) for item in check.run(repository, ".agent-policy.yml")}


def _append_stale_content(path: Path) -> None:
    path.write_text(path.read_text(encoding="utf-8") + "\nstale\n", encoding="utf-8")


def _assert_generated_output_collision(repository: Path, output_path: str) -> None:
    _write_repository(repository, output_path=output_path)

    render_diagnostics = render.run(repository, ".agent-policy.yml")
    assert len(render_diagnostics) == 1
    assert render_diagnostics[0].code == "RENDER"
    assert "Generated output paths overlap" in render_diagnostics[0].message

    check_diagnostics = check.run(repository, ".agent-policy.yml")
    assert len(check_diagnostics) == 1
    assert check_diagnostics[0].code == "RENDER"
    assert "Generated output paths overlap" in check_diagnostics[0].message

    assert not (repository / ".agent-policy.lock").exists()
    assert not (repository / ".agents").exists()


def _assert_reserved_lock_collision(repository: Path, output_path: str) -> None:
    _write_repository(repository, output_path=output_path)

    for command in (validate.run, render.run, check.run):
        diagnostics = command(repository, ".agent-policy.yml")
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "RESERVED_OUTPUT_PATH"
        assert diagnostics[0].path == output_path
        assert ".agent-policy.lock" in diagnostics[0].message

    assert not (repository / ".agent-policy.lock").exists()
    assert not (repository / ".agents").exists()
    assert not (repository / output_path).exists()


def _assert_lock_symlink_rejected(repository: Path) -> None:
    for command in (validate.run, render.run):
        diagnostics = command(repository, ".agent-policy.yml")
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "LOCK_PATH"
        assert diagnostics[0].path == ".agent-policy.lock"
        assert "must not be a symlink" in diagnostics[0].message

    check_diagnostics = check.run(repository, ".agent-policy.yml")
    assert len(check_diagnostics) == 1
    assert check_diagnostics[0].code == "CHECK"
    assert "must not be a symlink" in check_diagnostics[0].message

    assert not (repository / "AGENTS.md").exists()
    assert not (repository / ".agents").exists()


def test_check_uses_configured_agent_output_path(tmp_path: Path) -> None:
    output_path = ".agent-policy/preview/AGENTS.md"
    _write_repository(tmp_path, output_path=output_path)

    assert render.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []

    _append_stale_content(tmp_path / output_path)
    assert ("STALE_OUTPUT", output_path) in _diagnostic_pairs(tmp_path)


def test_check_reports_exact_stale_skill_file(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    skill_path = ".agents/skills/validate-agent-policy/SKILL.md"
    _append_stale_content(tmp_path / skill_path)

    assert ("STALE_OUTPUT", skill_path) in _diagnostic_pairs(tmp_path)


def test_check_reports_output_removed_from_configuration(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    config_path = tmp_path / ".agent-policy.yml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "enabled: true\n    path: AGENTS.md",
            "enabled: false\n    path: AGENTS.md",
        ),
        encoding="utf-8",
    )

    assert ("OBSOLETE_OUTPUT", "AGENTS.md") in _diagnostic_pairs(tmp_path)


def test_check_rejects_locked_output_outside_repository(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    lock_path = tmp_path / ".agent-policy.lock"
    lock_path.write_text(
        lock_path.read_text(encoding="utf-8").replace("  AGENTS.md:", "  ../outside:"),
        encoding="utf-8",
    )

    diagnostics = check.run(tmp_path, ".agent-policy.yml")
    assert diagnostics[0].code == "CHECK"
    assert "escapes repository root" in diagnostics[0].message


def test_render_rejects_exact_generated_output_collision(tmp_path: Path) -> None:
    _assert_generated_output_collision(
        tmp_path,
        ".agents/skills/validate-agent-policy/SKILL.md",
    )


def test_render_rejects_parent_generated_output_collision(tmp_path: Path) -> None:
    _assert_generated_output_collision(
        tmp_path,
        ".agents/skills/validate-agent-policy",
    )


def test_commands_reject_lock_file_as_agents_output(tmp_path: Path) -> None:
    _assert_reserved_lock_collision(tmp_path, ".agent-policy.lock")


def test_commands_reject_path_below_lock_file_as_agents_output(tmp_path: Path) -> None:
    _assert_reserved_lock_collision(tmp_path, ".agent-policy.lock/AGENTS.md")


def test_commands_reject_lock_symlink_outside_repository(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    outside_lock = tmp_path.parent / f"{tmp_path.name}-outside-lock"
    outside_lock.write_text("outside lock content\n", encoding="utf-8")
    lock_path = tmp_path / ".agent-policy.lock"
    try:
        lock_path.symlink_to(outside_lock)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    _assert_lock_symlink_rejected(tmp_path)

    assert outside_lock.read_text(encoding="utf-8") == "outside lock content\n"


def test_commands_reject_lock_symlink_to_repository_input(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    config_path = tmp_path / ".agent-policy.yml"
    config_content = config_path.read_text(encoding="utf-8")
    lock_path = tmp_path / ".agent-policy.lock"
    try:
        lock_path.symlink_to(config_path.name)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    _assert_lock_symlink_rejected(tmp_path)

    assert config_path.read_text(encoding="utf-8") == config_content

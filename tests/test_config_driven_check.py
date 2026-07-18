from pathlib import Path

from agent_policy.commands import check, render

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

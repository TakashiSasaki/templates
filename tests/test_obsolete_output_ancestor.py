from pathlib import Path

from agent_policy.commands import render


PROJECT_POLICY = """---
id: project.rule
severity: mandatory
overridable: true
order: 1000
---
# Rule

Body.
"""


def _write_repository(repository: Path) -> None:
    (repository / ".git").mkdir()
    (repository / "policy").mkdir()
    (repository / "policy/project.md").write_text(
        PROJECT_POLICY,
        encoding="utf-8",
    )
    (repository / ".agent-policy.yml").write_text(
        """schema_version: 1
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
    enabled: true
    path: AGENTS.md
skills:
  enabled:
    - validate-agent-policy
""",
        encoding="utf-8",
    )


def test_render_rejects_obsolete_file_ancestor_before_nested_write(
    tmp_path: Path,
) -> None:
    _write_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    obsolete = tmp_path / "AGENTS.md"
    original_output = obsolete.read_bytes()
    lock = tmp_path / ".agent-policy.lock"
    original_lock = lock.read_bytes()

    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "path: AGENTS.md",
            "path: AGENTS.md/index.md",
        ),
        encoding="utf-8",
    )

    diagnostics = render.run(tmp_path, ".agent-policy.yml")

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "RENDER"
    assert (
        diagnostics[0].message
        == "Refusing to replace obsolete generated file with nested output: "
        "AGENTS.md is an ancestor of AGENTS.md/index.md"
    )
    assert obsolete.is_file()
    assert obsolete.read_bytes() == original_output
    assert not (tmp_path / "AGENTS.md/index.md").exists()
    assert lock.read_bytes() == original_lock

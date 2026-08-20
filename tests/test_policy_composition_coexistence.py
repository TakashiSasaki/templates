from __future__ import annotations

from pathlib import Path

from agent_policy.commands import adopt, init, validate


def _write_project_policy(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """---
id: project.rule
severity: mandatory
overridable: true
order: 1000
---
# Rule

Body.
""",
        encoding="utf-8",
    )


def test_default_init_preserves_composition_metadata(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    composition = tmp_path / ".template-composition"
    composition.mkdir()
    lock = composition / "lock.json"
    original = b'{"schema_version":2,"owner":"composition"}\n'
    lock.write_bytes(original)

    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        enabled_skills=[],
    )

    assert diagnostics == []
    assert lock.read_bytes() == original
    assert (tmp_path / ".agent-policy.yml").is_file()
    assert (tmp_path / ".agent-policy.lock").is_file()


def test_init_rejects_output_inside_composition_namespace_before_writing(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        agents_output_path=".template-composition/AGENTS.md",
        enabled_skills=[],
    )

    assert diagnostics[0].code == "INIT_AGENTS_OUTPUT_PATH"
    assert ".template-composition" in diagnostics[0].message
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / "policy/project.md").exists()
    assert not (tmp_path / ".template-composition/AGENTS.md").exists()


def test_validate_rejects_composition_namespace_as_policy_input(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    foreign_policy = tmp_path / ".template-composition/policy.md"
    _write_project_policy(foreign_policy)
    (tmp_path / ".agent-policy.yml").write_text(
        """schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: LOCAL-DEVELOPMENT
contexts:
  default:
    profiles:
      - core
    project_policy:
      files:
        - .template-composition/policy.md
outputs:
  agents:
    enabled: true
    path: AGENTS.md
    context: default
    renderer: agents-md
skills:
  enabled: []
""",
        encoding="utf-8",
    )

    diagnostics = validate.run(tmp_path, ".agent-policy.yml")

    assert any(item.code == "POLICY_PATH" for item in diagnostics)
    assert any(".template-composition" in item.message for item in diagnostics)
    assert foreign_policy.is_file()


def test_adoption_rejects_composition_namespace_as_policy_state(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        state_path=".template-composition/adoption.json",
        enabled_skills=[],
    )

    assert diagnostics[0].code == "ADOPT_PREPARE"
    assert ".template-composition" in diagnostics[0].message
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / ".template-composition/adoption.json").exists()

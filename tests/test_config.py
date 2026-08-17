from pathlib import Path

from agent_policy.commands import validate
from agent_policy.config import load_config, validate_config


def _write_project_policy(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "policy").mkdir()
    (tmp_path / "policy/project.md").write_text(
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


def test_example_configuration_is_valid(tmp_path: Path) -> None:
    _write_project_policy(tmp_path)
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
        - policy/project.md
outputs:
  agents:
    enabled: true
    path: AGENTS.md
    context: default
    renderer: agents-md
skills:
  enabled:
    - validate-agent-policy
""",
        encoding="utf-8",
    )
    config = load_config(tmp_path, ".agent-policy.yml")
    assert validate_config(tmp_path, config) == []


def test_schema_version_one_is_rejected(tmp_path: Path) -> None:
    _write_project_policy(tmp_path)
    (tmp_path / ".agent-policy.yml").write_text(
        """schema_version: 1
toolchain:
  repository: TakashiSasaki/templates
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
  enabled: []
""",
        encoding="utf-8",
    )
    config = load_config(tmp_path, ".agent-policy.yml")
    diagnostics = validate_config(tmp_path, config)
    assert any(item.code == "SCHEMA" for item in diagnostics)

    command_diagnostics = validate.run(tmp_path, ".agent-policy.yml")
    assert any(item.code == "SCHEMA" for item in command_diagnostics)


def test_v2_rejects_top_level_profiles_and_project_policy(tmp_path: Path) -> None:
    _write_project_policy(tmp_path)
    (tmp_path / ".agent-policy.yml").write_text(
        """schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
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
    context: default
    renderer: agents-md
skills:
  enabled: []
""",
        encoding="utf-8",
    )
    config = load_config(tmp_path, ".agent-policy.yml")
    diagnostics = validate_config(tmp_path, config)
    assert any(item.code == "SCHEMA" for item in diagnostics)

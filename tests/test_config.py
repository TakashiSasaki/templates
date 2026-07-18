from pathlib import Path

from agent_policy.config import load_config, validate_config


def test_example_configuration_is_valid(tmp_path: Path) -> None:
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
    (tmp_path / ".agent-policy.yml").write_text(
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
    config = load_config(tmp_path, ".agent-policy.yml")
    assert validate_config(tmp_path, config) == []

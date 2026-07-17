from pathlib import Path

from agent_policy.config import load_config, validate_config


def test_example_configuration_is_valid(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "policy").mkdir()
    (tmp_path / "policy/project.md").write_text(
        "---\nid: project.rule\nseverity: mandatory\noverridable: true\norder: 1000\n---\n# Rule\n\nBody.\n",
        encoding="utf-8",
    )
    (tmp_path / ".agent-policy.yml").write_text(
        """schema_version: 1\ntoolchain:\n  repository: TakashiSasaki/agent-policy\n  revision: LOCAL-DEVELOPMENT\nprofiles:\n  - core\nproject_policy:\n  files:\n    - policy/project.md\noutputs:\n  agents:\n    enabled: true\n    path: AGENTS.md\nskills:\n  enabled:\n    - validate-agent-policy\n""",
        encoding="utf-8",
    )
    config = load_config(tmp_path, ".agent-policy.yml")
    assert validate_config(tmp_path, config) == []

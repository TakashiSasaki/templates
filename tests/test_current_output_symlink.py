from pathlib import Path

import pytest

from agent_policy.commands import render
from agent_policy.renderer import GENERATED_MARKER


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
    (repository / "policy/project.md").write_text(PROJECT_POLICY, encoding="utf-8")
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
  enabled: []
""",
        encoding="utf-8",
    )


def test_render_allows_existing_current_output_symlink(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    target_path = tmp_path / "generated-copy.md"
    target_path.write_text(f"{GENERATED_MARKER}\n", encoding="utf-8")
    agents_path = tmp_path / "AGENTS.md"
    try:
        agents_path.symlink_to(target_path.name)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    assert render.run(tmp_path, ".agent-policy.yml") == []
    first_content = target_path.read_text(encoding="utf-8")
    assert agents_path.is_symlink()

    assert render.run(tmp_path, ".agent-policy.yml") == []
    assert agents_path.is_symlink()
    assert target_path.read_text(encoding="utf-8") == first_content

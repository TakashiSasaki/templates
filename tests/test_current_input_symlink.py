from pathlib import Path

import pytest

from agent_policy.commands import render
from agent_policy.lockfile import sha256_file
from agent_policy.yamlutil import dump_yaml, load_yaml

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


def _replace_locked_outputs(repository: Path, relative: str) -> None:
    lock_path = repository / ".agent-policy.lock"
    lock = load_yaml(lock_path)
    assert isinstance(lock, dict)
    lock["outputs"] = {relative: {"sha256": sha256_file(repository / relative)}}
    lock_path.write_text(dump_yaml(lock), encoding="utf-8")


@pytest.mark.parametrize("relative", [".agent-policy.yml", "policy/project.md"])
def test_render_preserves_symlinked_current_input_listed_as_obsolete_output(
    tmp_path: Path,
    relative: str,
) -> None:
    _write_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    input_path = tmp_path / relative
    target_path = input_path.with_name(f"{input_path.name}.target")
    original = input_path.read_bytes()
    target_path.write_bytes(original)
    input_path.unlink()
    try:
        input_path.symlink_to(target_path.name)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    _replace_locked_outputs(tmp_path, relative)

    assert render.run(tmp_path, ".agent-policy.yml") == []
    assert input_path.is_symlink()
    assert target_path.read_bytes() == original

    lock = load_yaml(tmp_path / ".agent-policy.lock")
    assert isinstance(lock, dict)
    assert relative not in lock["outputs"]

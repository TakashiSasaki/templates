from pathlib import Path

from agent_policy.commands import render
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


def _write_repository(repository: Path, *, output_path: str = "AGENTS.md") -> None:
    (repository / ".git").mkdir()
    (repository / "policy").mkdir()
    (repository / "policy/project.md").write_text(
        PROJECT_POLICY,
        encoding="utf-8",
    )
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
    enabled: true
    path: {output_path}
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


def test_render_rejects_obsolete_descendant_before_parent_write(
    tmp_path: Path,
) -> None:
    _write_repository(tmp_path, output_path="AGENTS.md/index.md")
    assert render.run(tmp_path, ".agent-policy.yml") == []

    obsolete = tmp_path / "AGENTS.md/index.md"
    original_output = obsolete.read_bytes()
    lock = tmp_path / ".agent-policy.lock"
    original_lock = lock.read_bytes()

    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "path: AGENTS.md/index.md",
            "path: AGENTS.md",
        ),
        encoding="utf-8",
    )

    diagnostics = render.run(tmp_path, ".agent-policy.yml")

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "RENDER"
    assert (
        diagnostics[0].message
        == "Refusing to replace obsolete nested output with parent output: "
        "AGENTS.md/index.md is a descendant of AGENTS.md"
    )
    assert (tmp_path / "AGENTS.md").is_dir()
    assert obsolete.read_bytes() == original_output
    assert lock.read_bytes() == original_lock


def test_render_rejects_duplicate_normalized_obsolete_targets(
    tmp_path: Path,
) -> None:
    _write_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    obsolete = tmp_path / "AGENTS.md"
    original_output = obsolete.read_bytes()
    lock_path = tmp_path / ".agent-policy.lock"
    lock = load_yaml(lock_path)
    assert isinstance(lock, dict)
    outputs = lock["outputs"]
    assert isinstance(outputs, dict)
    metadata = outputs["AGENTS.md"]
    assert isinstance(metadata, dict)
    lock["outputs"] = {
        "AGENTS.md": dict(metadata),
        "./AGENTS.md": dict(metadata),
    }
    lock_path.write_text(dump_yaml(lock), encoding="utf-8")
    duplicate_lock = lock_path.read_bytes()

    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "enabled: true\n    path: AGENTS.md",
            "enabled: false\n    path: AGENTS.md",
        ),
        encoding="utf-8",
    )

    diagnostics = render.run(tmp_path, ".agent-policy.yml")

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "RENDER"
    assert "Lock output paths normalize to the same target" in diagnostics[0].message
    assert "AGENTS.md" in diagnostics[0].message
    assert "./AGENTS.md" in diagnostics[0].message
    assert obsolete.read_bytes() == original_output
    assert lock_path.read_bytes() == duplicate_lock

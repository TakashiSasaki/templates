from __future__ import annotations

import hashlib
from pathlib import Path

from agent_policy.commands import adopt, init, render, validate
from agent_policy.yamlutil import dump_yaml, load_yaml

ROOT = Path(__file__).resolve().parents[1]
TEST_TOOLCHAIN_SHA = "7" * 40


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
        toolchain_revision=TEST_TOOLCHAIN_SHA,
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
        toolchain_revision=TEST_TOOLCHAIN_SHA,
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
        f"""schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {TEST_TOOLCHAIN_SHA}
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
        toolchain_revision=TEST_TOOLCHAIN_SHA,
        profiles=["core"],
        state_path=".template-composition/adoption.json",
        enabled_skills=[],
    )

    assert diagnostics[0].code == "ADOPT_PREPARE"
    assert ".template-composition" in diagnostics[0].message
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / ".template-composition/adoption.json").exists()


def test_render_does_not_clean_up_foreign_path_claimed_by_old_policy_lock(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision=TEST_TOOLCHAIN_SHA,
        profiles=["core"],
        enabled_skills=[],
    )
    assert diagnostics == []

    foreign = tmp_path / ".template-composition/foreign.md"
    foreign.parent.mkdir(exist_ok=True)
    foreign_bytes = b"composition-owned\n"
    foreign.write_bytes(foreign_bytes)

    policy_lock = tmp_path / ".agent-policy.lock"
    lock = load_yaml(policy_lock)
    assert isinstance(lock, dict)
    outputs = lock["outputs"]
    assert isinstance(outputs, dict)
    outputs[".template-composition/foreign.md"] = {
        "sha256": hashlib.sha256(foreign_bytes).hexdigest()
    }
    policy_lock.write_text(dump_yaml(lock), encoding="utf-8")
    lock_before = policy_lock.read_bytes()

    diagnostics = render.run(tmp_path, ".agent-policy.yml")

    assert diagnostics[0].code == "RENDER"
    assert ".template-composition" in diagnostics[0].message
    assert foreign.read_bytes() == foreign_bytes
    assert policy_lock.read_bytes() == lock_before


def test_policy_docs_use_current_authority_topology() -> None:
    paths = [
        ROOT / "README.md",
        ROOT / "docs/architecture.md",
        ROOT / "docs/publication-catalog.md",
        ROOT / "docs/repository-structure.md",
        ROOT / "docs/adr/0003-application-neutral-policy-scope.md",
        ROOT / "docs/adr/0006-copyable-artifact-policy-adoption.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    stale_active_topology = [
        "repository's `skill`, `site`, and `webapp` branches",
        "`main`, `site`, and `webapp` branches",
        "together with the `skill` and `webapp` catalogs",
        "branch `webapp`",
        "The `skill` and `webapp` branches each publish",
    ]
    for phrase in stale_active_topology:
        assert phrase not in combined

    assert "https://templates.moukaeritai.work/coexistence/" in combined
    assert ".template-composition/**" in combined
    assert "composition` authority" in combined

from __future__ import annotations

from pathlib import Path

from agent_policy.commands import render, validate

TEST_REVISION = "a" * 40
OVERRIDABLE_ID = "consistency.synchronize-derived-artifacts"
NON_OVERRIDABLE_ID = "changes.minimize-scope"


def _policy(rule_id: str, title: str, order: int = 1000) -> str:
    return f"""---
id: {rule_id}
severity: mandatory
overridable: true
order: {order}
---
# {title}

Repository-specific replacement.
"""


def _write_v2(
    repository: Path,
    *,
    policy_files: list[str],
    overrides: list[tuple[str, str]],
) -> None:
    (repository / ".git").mkdir(exist_ok=True)
    lines = [
        "schema_version: 2",
        "toolchain:",
        "  repository: TakashiSasaki/templates",
        f"  revision: {TEST_REVISION}",
        "contexts:",
        "  coding:",
        "    profiles:",
        "      - core",
        "    project_policy:",
        "      files:",
    ]
    lines.extend(f"        - {path}" for path in policy_files)
    if overrides:
        lines.append("    overrides:")
        for rule_id, reason in overrides:
            lines.extend(
                [
                    f"      - id: {rule_id}",
                    f"        reason: {reason}",
                ]
            )
    lines.extend(
        [
            "outputs:",
            "  agents:",
            "    enabled: true",
            "    path: AGENTS.md",
            "    context: coding",
            "    renderer: agents-md",
            "skills:",
            "  enabled: []",
        ]
    )
    (repository / ".agent-policy.yml").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _write_policy(repository: Path, relative: str, content: str) -> None:
    path = repository / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _composition_messages(repository: Path) -> list[str]:
    return [
        item.message
        for item in validate.run(repository, ".agent-policy.yml")
        if item.code == "POLICY_COMPOSITION"
    ]


def test_v2_requires_explicit_override_declaration(tmp_path: Path) -> None:
    relative = "policy/override.md"
    _write_policy(tmp_path, relative, _policy(OVERRIDABLE_ID, "Local replacement"))
    _write_v2(tmp_path, policy_files=[relative], overrides=[])

    messages = _composition_messages(tmp_path)
    assert len(messages) == 1
    assert f"override for {OVERRIDABLE_ID} must be declared" in messages[0]


def test_v2_accepts_declared_override_with_reason(tmp_path: Path) -> None:
    relative = "policy/override.md"
    _write_policy(tmp_path, relative, _policy(OVERRIDABLE_ID, "Local replacement"))
    _write_v2(
        tmp_path,
        policy_files=[relative],
        overrides=[(OVERRIDABLE_ID, "Repository generation process is authoritative")],
    )

    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert render.run(tmp_path, ".agent-policy.yml") == []
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "Local replacement" in agents
    assert "Keep derived artifacts synchronized" not in agents


def test_v2_rejects_stale_override_declaration(tmp_path: Path) -> None:
    relative = "policy/local.md"
    _write_policy(tmp_path, relative, _policy("project.local", "Local rule"))
    _write_v2(
        tmp_path,
        policy_files=[relative],
        overrides=[(OVERRIDABLE_ID, "No replacement actually exists")],
    )

    messages = _composition_messages(tmp_path)
    assert len(messages) == 1
    assert "Declared overrides do not replace shared rules" in messages[0]
    assert OVERRIDABLE_ID in messages[0]


def test_v2_rejects_non_overridable_shared_rule(tmp_path: Path) -> None:
    relative = "policy/override.md"
    _write_policy(tmp_path, relative, _policy(NON_OVERRIDABLE_ID, "Forbidden replacement"))
    _write_v2(
        tmp_path,
        policy_files=[relative],
        overrides=[(NON_OVERRIDABLE_ID, "Attempted local exception")],
    )

    messages = _composition_messages(tmp_path)
    assert len(messages) == 1
    assert f"Rule {NON_OVERRIDABLE_ID} is not overridable" in messages[0]


def test_v2_rejects_duplicate_repository_rule_ids(tmp_path: Path) -> None:
    first = "policy/first.md"
    second = "policy/second.md"
    _write_policy(tmp_path, first, _policy("project.duplicate", "First local rule", 1000))
    _write_policy(tmp_path, second, _policy("project.duplicate", "Second local rule", 1010))
    _write_v2(tmp_path, policy_files=[first, second], overrides=[])

    messages = _composition_messages(tmp_path)
    assert len(messages) == 1
    assert "Duplicate repository rule ID project.duplicate" in messages[0]


def test_v2_rejects_duplicate_override_ids(tmp_path: Path) -> None:
    relative = "policy/override.md"
    _write_policy(tmp_path, relative, _policy(OVERRIDABLE_ID, "Local replacement"))
    _write_v2(
        tmp_path,
        policy_files=[relative],
        overrides=[
            (OVERRIDABLE_ID, "First reason"),
            (OVERRIDABLE_ID, "Second reason"),
        ],
    )

    diagnostics = validate.run(tmp_path, ".agent-policy.yml")
    assert any(item.code == "DUPLICATE_OVERRIDE" for item in diagnostics)

from __future__ import annotations

from pathlib import Path

from agent_policy.commands import check, render, validate
from agent_policy.yamlutil import load_yaml

TEST_REVISION = "a" * 40
LOCAL_POLICY = """---
id: {rule_id}
severity: mandatory
overridable: true
order: 1000
---
# {title}

{body}
"""


def _write_v2_repository(repository: Path) -> None:
    (repository / ".git").mkdir()
    (repository / "policy").mkdir()
    (repository / "policy/coding.md").write_text(
        LOCAL_POLICY.format(
            rule_id="project.coding-only",
            title="Coding-only repository rule",
            body="Apply this rule only to the coding context.",
        ),
        encoding="utf-8",
    )
    (repository / "policy/review.md").write_text(
        LOCAL_POLICY.format(
            rule_id="project.review-only",
            title="Review-only repository rule",
            body="Apply this rule only to the review context.",
        ),
        encoding="utf-8",
    )
    (repository / ".agent-policy.yml").write_text(
        f"""schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {TEST_REVISION}
contexts:
  coding:
    profiles:
      - core
    project_policy:
      files:
        - policy/coding.md
  review:
    profiles:
      - core
      - security-baseline
      - review
    project_policy:
      files:
        - policy/review.md
outputs:
  agents:
    enabled: true
    path: AGENTS.md
    context: coding
    renderer: agents-md
  review-guidelines:
    enabled: true
    path: .agents/review/REVIEW_GUIDELINES.md
    context: review
    renderer: policy-context-md
  review-github-json:
    enabled: true
    path: .agents/review/GITHUB_REVIEW_JSON_V1.md
    context: review
    renderer: github-review-json-v1
skills:
  enabled: []
""",
        encoding="utf-8",
    )


def test_v2_renders_distinct_policy_contexts(tmp_path: Path) -> None:
    _write_v2_repository(tmp_path)

    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert render.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []

    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    review = (tmp_path / ".agents/review/REVIEW_GUIDELINES.md").read_text(
        encoding="utf-8"
    )

    assert "project.coding-only" in agents
    assert "project.review-only" not in agents
    assert "review.require-change-causality" not in agents

    assert "project.review-only" in review
    assert "project.coding-only" not in review
    assert "review.require-change-causality" in review
    assert "security.validate-boundaries" in review
    assert "renderer: policy-context-md" in review

    lock = load_yaml(tmp_path / ".agent-policy.lock")
    assert isinstance(lock, dict)
    assert set(lock["inputs"]) == {
        ".agent-policy.yml",
        "policy/coding.md",
        "policy/review.md",
    }
    assert set(lock["outputs"]) == {
        "AGENTS.md",
        ".agents/review/REVIEW_GUIDELINES.md",
        ".agents/review/GITHUB_REVIEW_JSON_V1.md",
    }


def test_v2_renders_github_review_json_as_adapter_only(tmp_path: Path) -> None:
    _write_v2_repository(tmp_path)

    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert render.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []

    semantic = (tmp_path / ".agents/review/REVIEW_GUIDELINES.md").read_text(
        encoding="utf-8"
    )
    adapter = (tmp_path / ".agents/review/GITHUB_REVIEW_JSON_V1.md").read_text(
        encoding="utf-8"
    )

    assert "renderer: policy-context-md" in semantic
    assert "project.review-only" in semantic
    assert "review.require-change-causality" in semantic
    assert "security.validate-boundaries" in semantic

    assert "renderer: github-review-json-v1" in adapter
    assert "does not contain or redefine semantic review policy" in adapter
    assert "Policy context: `review`" in adapter
    assert "project.review-only" not in adapter
    assert "review.require-change-causality" not in adapter
    assert "security.validate-boundaries" not in adapter
    assert '"analysis_status": "COMPLETE"' in adapter
    assert '"event": "REQUEST_CHANGES"' in adapter
    assert '"side": "RIGHT"' in adapter
    assert '"schema_version": 1' in adapter
    assert "exactly one standard JSON object" in adapter


def test_v2_rejects_unknown_output_context(tmp_path: Path) -> None:
    _write_v2_repository(tmp_path)
    config_path = tmp_path / ".agent-policy.yml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "context: review\n    renderer: policy-context-md",
            "context: missing\n    renderer: policy-context-md",
            1,
        ),
        encoding="utf-8",
    )

    diagnostics = validate.run(tmp_path, ".agent-policy.yml")
    assert any(
        item.code == "UNKNOWN_CONTEXT"
        and item.path == "outputs.review-guidelines.context"
        for item in diagnostics
    )

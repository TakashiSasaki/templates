from __future__ import annotations

from pathlib import Path

from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/pr-review"


def test_pr_review_skill_layout_and_config_path_rendering() -> None:
    rendered = render_skill("pr-review", config_path="config/agent-policy.yml")

    assert set(rendered) == {
        "SKILL.md",
        "references/canonical-github-pr-review-prompt.md",
    }
    assert "{{ config_path }}" not in rendered["SKILL.md"]
    assert "{{ config_path }}" not in rendered[
        "references/canonical-github-pr-review-prompt.md"
    ]
    assert "config/agent-policy.yml" in rendered["SKILL.md"]
    assert "config/agent-policy.yml" in rendered[
        "references/canonical-github-pr-review-prompt.md"
    ]


def test_pr_review_skill_keeps_semantics_adapter_and_merge_gate_separate() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "read-only" in skill
    assert "exact current base and head revisions" in skill
    assert "provider-neutral review-policy output" in skill
    assert "platform adapter output" in skill
    assert "not by itself a code defect" in skill
    assert "resolve the pull-request head again" in skill
    assert "Do not merge the pull request" in skill
    assert "separate merge-gate procedure" in skill


def test_canonical_prompt_is_orchestration_not_semantic_or_transport_authority() -> None:
    prompt = (
        SKILL_ROOT / "references/canonical-github-pr-review-prompt.md"
    ).read_text(encoding="utf-8")

    assert "independent pull-request review agent" in prompt
    assert "current base revision" in prompt
    assert "current head revision" in prompt
    assert "review-policy output" in prompt
    assert "GitHub review adapter" in prompt
    assert "claims to verify" in prompt
    assert "Pending, skipped, stale, inaccessible, or missing evidence is not a pass" in prompt
    assert "If it changed, the prior analysis is stale" in prompt
    assert "Do not merge" in prompt
    assert "merge-authorization decision" in prompt

    # Semantic severity definitions and GitHub transport vocabulary must remain
    # owned by the loaded policy and adapter rather than copied into the prompt.
    forbidden = (
        "REQUEST_CHANGES",
        "APPROVE",
        "COMMENT",
        '"schema_version"',
        '"analysis_status"',
        "LEFT",
        "RIGHT",
        "confidence >=",
        "confidence at least",
    )
    for term in forbidden:
        assert term not in prompt


def test_canonical_prompt_does_not_turn_ci_incompleteness_into_a_defect() -> None:
    prompt = (
        SKILL_ROOT / "references/canonical-github-pr-review-prompt.md"
    ).read_text(encoding="utf-8")

    assert "incompleteness alone is not a code defect" in prompt
    assert "represent material uncertainty as a review limitation" in prompt

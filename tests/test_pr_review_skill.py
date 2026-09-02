from __future__ import annotations

from pathlib import Path

from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/pr-review"
AGENT_POLICY_SKILL = ROOT / "skills/agent-policy/SKILL.md"


def test_pr_review_skill_layout_is_provider_neutral() -> None:
    rendered = render_skill("pr-review", config_path="config/agent-policy.yml")

    assert set(rendered) == {
        "SKILL.md",
        "references/github-pull-request-review-api.md",
    }
    assert "github-review-json-adapter-v1" not in rendered["SKILL.md"]
    assert '"analysis_status"' not in rendered["SKILL.md"]
    assert '"schema_version"' not in rendered["SKILL.md"]
    assert '"unanchored_findings"' not in rendered["SKILL.md"]


def test_pr_review_is_sole_identity_bound_procedure_authority() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    required = (
        "sole procedural authority",
        "stable repository identity",
        "pull-request identity",
        "exact trusted base commit and tree",
        "complete set of best common ancestors",
        "exactly one commit",
        "unique-merge-base-to-head changed surface",
        "current exact-head CI",
        "provider-neutral semantic review policy",
        "Preserve limitations and incomplete evidence",
        "Form the conceptual review conclusion",
        "Refresh all live identities immediately before completion",
        "Invalidate evidence on drift",
        "identity-bound completion handoff",
        "Do not merge the pull request",
        "separate merge-gate procedure",
    )
    for text in required:
        assert text in skill


def test_pr_review_conclusion_is_not_provider_serialization() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "completed review with blocking findings" in skill
    assert "completed review with no blocking findings" in skill
    assert "incomplete review with preserved limitations or failure evidence" in skill
    assert "not a provider event" in skill
    assert "no required JSON representation" in skill
    assert "Provider serialization never becomes normative review authority" in skill

    forbidden = (
        "github-review-json-adapter-v1",
        '"schema_version"',
        '"analysis_status"',
        '"unanchored_findings"',
        '"event": "APPROVE"',
        '"event": "REQUEST_CHANGES"',
        '"event": "COMMENT"',
    )
    for text in forbidden:
        assert text not in skill


def test_pr_review_drift_rules_preserve_authority_boundaries() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "Base movement changes the review-policy authority root" in skill
    assert "Base movement:" in skill
    assert "invalidate the entire trusted authority closure and all analysis" in skill
    assert "Head movement:" in skill
    assert "invalidate the changed surface and every finding" in skill
    assert "Merge-base movement or loss of uniqueness:" in skill
    assert "return to the authenticated bootstrap" in skill
    assert "completion handoff" in skill
    assert "immediately re-resolve" in skill
    assert "Any mismatch makes the handoff stale" in skill


def test_pr_review_delegates_ci_classification_to_semantic_policy() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "Collect current exact-head CI and validation evidence" in skill
    assert "Do **not** define the semantic meaning of those states here" in skill
    assert "Pass the observations to the bound semantic review policy for classification" in skill
    assert "Do not convert incomplete analysis into a successful review" in skill


def test_agent_policy_bootstrap_freezes_provider_neutral_review_authority() -> None:
    bootstrap = AGENT_POLICY_SKILL.read_text(encoding="utf-8")

    required = (
        "## Trusted `pr-review` bootstrap",
        "must not perform finding analysis",
        "frozen bootstrap run image",
        "exact-base Git-object-backed snapshot",
        "frozen runtime",
        "trusted-snapshot `validate` and `check`",
        "enable `pr-review`",
        "renderer is exactly `policy-context-md`",
        "review-bundle",
        "The materialized bundle is not yet trusted",
        "freeze it",
        "complete lock-authoritative generated `pr-review` Skill tree",
        "No provider adapter or provider result serializer",
        "immutable bootstrap handoff",
        "The proposed head is never an authority input to bootstrap",
    )
    for text in required:
        assert text in bootstrap


def test_github_reference_marks_every_json_sample_non_normative() -> None:
    reference = (
        SKILL_ROOT / "references/github-pull-request-review-api.md"
    ).read_text(encoding="utf-8")

    assert "non-normative provider integration reference" in reference
    assert "current GitHub API or connected-tool contract is authoritative" in reference
    for text in (
        "body",
        "commit_id",
        "APPROVE",
        "REQUEST_CHANGES",
        "COMMENT",
        "path",
        "line",
        "side",
        "start_line",
        "start_side",
    ):
        assert text in reference

    disclaimer = (
        "GitHub API request example only; it is NOT the required output format of `pr-review`."
    )
    assert reference.count("```json") == 3
    assert reference.count(disclaimer) == reference.count("```json")
    assert "No JSON example in this document is a review-result schema" in reference

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
    for content in rendered.values():
        assert "agent-policy-generated: true" in content
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
        "provider-neutral semantic review-policy bytes",
        "Preserve limitations, execution failures, and incomplete analysis",
        "Form the conceptual review conclusion only after completion is established",
        "Refresh all live identities immediately before completion",
        "Invalidate evidence on drift",
        "identity-bound completion handoff",
        "Do not merge the pull request",
        "separate merge-gate procedure",
    )
    for text in required:
        assert text in skill


def test_pr_review_models_observed_behavior_before_change_authored_claims() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "independent observed-change model" in skill
    assert "Before using pull-request descriptions" in skill
    assert "Observed" in skill
    assert "Claimed" in skill
    assert "Required" in skill
    assert "Use Claimed information as hypotheses or evidence" in skill
    assert "stated design intent from silently defining the review search space" in skill


def test_pr_review_separates_candidate_discovery_from_finding_acceptance() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    required = (
        "Generate defect candidates broadly",
        "A **candidate** is an investigation target, not a finding",
        "construct a concrete counterexample",
        "state or input **X**",
        "required invariant **Z**",
        "Aggressively falsify each candidate before promoting it",
        "existing guard already prevents the scenario",
        "Discard candidates that are falsified, unreachable, outside change causality",
        "Promote only verified candidates to findings",
    )
    for text in required:
        assert text in skill


def test_pr_review_traces_real_consumers_without_contaminating_changed_surface() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "Trace realistic consumers and execution paths" in skill
    assert "at least one realistic downstream path" in skill
    assert "what is actually consumed and executed" in skill
    assert "unchanged consumer files are context rather than part of the changed surface" in skill


def test_pr_review_requires_substantive_completion_not_merely_output() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    required = (
        "transient coverage and completion working state",
        "not a repository-owned review-result schema",
        "prevent an unperformed analysis from being mistaken for a zero-finding analysis",
        "Producing text is not proof that a review completed",
        "delegation status, or work progress does not satisfy the required analysis passes",
        "Finding count is not completion evidence",
        "If substantive review work did not complete, use the third form",
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
    assert "candidate, falsification result, coverage/completion disposition" in skill
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
    assert "Green CI is evidence, not proof" in skill
    assert "Do not convert incomplete analysis into a successful review" in skill


def test_agent_policy_bootstrap_freezes_provider_neutral_review_authority() -> None:
    bootstrap = AGENT_POLICY_SKILL.read_text(encoding="utf-8")

    required = (
        "## Trusted `pr-review` bootstrap",
        "must not perform finding analysis",
        "bootstrap run image",
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

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from agent_policy.config import package_root
from agent_policy.policy_loader import parse_policy
from agent_policy.renderer import NON_GENERATED_SKILLS, render_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "pr-merge-gate" / "SKILL.md"
PROFILE = ROOT / "profiles" / "pull-request.yml"
FEEDBACK_REFERENCE = SKILL.parent / "references" / "review-feedback-disposition.md"


def _profile_rule_ids() -> list[str]:
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    return [
        parse_policy(ROOT / path, path, "toolchain").id
        for path in profile["policy_files"]
    ]


def test_adapter_has_stable_agent_skill_identity() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, frontmatter, body = text.split("---\n", 2)
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == "pr-merge-gate"
    assert isinstance(metadata["description"], str) and metadata["description"]
    assert re.fullmatch(r"[a-z0-9-]+", SKILL.parent.name)
    assert body.lstrip().startswith("# Pull Request Merge Gate\n")


def test_adapter_references_every_canonical_pull_request_rule() -> None:
    text = SKILL.read_text(encoding="utf-8")
    rule_ids = _profile_rule_ids()
    assert rule_ids
    for rule_id in rule_ids:
        assert f"`{rule_id}`" in text


def test_adapter_declares_policy_authority_boundary() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "not a second authority for shared pull-request semantics",
        "the rules under `policy/pull-request/` are canonical",
        "this skill owns github-specific execution details, not shared policy meaning",
        "if this skill conflicts with those canonical rules, follow the canonical rules",
        "if the `pull-request` profile changes, this adapter must be reviewed",
    ):
        assert invariant in text


def test_adapter_is_excluded_from_generated_skill_catalog() -> None:
    skill_name = "pr-merge-gate"
    assert (package_root() / "skills" / skill_name).is_dir()
    assert skill_name in NON_GENERATED_SKILLS

    with pytest.raises(ValueError, match=f"Unknown generated skill: {skill_name}"):
        render_skill(skill_name)


def test_adapter_keeps_provider_mechanics_outside_atomic_policy() -> None:
    adapter = SKILL.read_text(encoding="utf-8")
    policy_corpus = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "policy" / "pull-request").glob("*.md")
    )

    adapter_terms = (
        "GitHub connector",
        "expected_head_sha",
        "check-run",
        "check-suite",
        "CI_DISCOVERY_MIN_OBSERVATION_MINUTES = 10",
    )
    for term in adapter_terms:
        assert term in adapter
        assert term not in policy_corpus


def test_adapter_does_not_embed_transient_reviewer_triggers() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    assert "@hermes review" not in text
    assert "hermes agent" not in text


def test_adapter_ci_discovery_is_fail_closed_and_read_only() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "`ci_discovery_pending`",
        "`ci_confirmed_absent`",
        "use read-only discovery",
        "at least two independently indexed github views",
        "a single zero-result view",
        "elapsed time alone is insufficient",
        "do not close/reopen the pr",
        "create a no-op commit",
        "solely to retrigger ci",
    ):
        assert invariant in text


def test_adapter_reuses_valid_evidence_and_forbids_agent_overconstraint() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "do not discard the whole snapshot merely because one binding changes",
        "invalidate the evidence bound to the former head",
        "do not repeat a successful observation merely for conservatism",
        (
            "do not add an extra review cycle, waiting period, repeated live-state "
            "read, or redundant evidence collection as a new mandatory gate"
        ),
        (
            "reuse it while the exact head and the conditions that determine check "
            "applicability remain unchanged"
        ),
        (
            "do not rerun ci discovery or re-fetch workflow definitions solely to "
            "make an already valid result feel newer"
        ),
        "do not request another independent review merely for conservatism",
        "do not treat target-branch movement as an automatic instruction to rerun every gate",
        "reacquire only the affected evidence",
        "diagnostic work rather than new mandatory acceptance requirements",
        (
            "do not create additional stop conditions solely because a stricter "
            "local procedure feels safer"
        ),
    ):
        assert invariant in text


def test_adapter_final_refresh_is_invalidation_driven() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "refresh invalidating live state",
        "current pr head equals the exact accepted head",
        "current target-branch head is unchanged or its movement has been evaluated",
        "current material review state and unresolved review threads",
        (
            "validate the binding facts of previously accepted scope, ci, and "
            "completed-review evidence"
        ),
        (
            "do not unconditionally re-fetch exact-head checks, completed reviews, "
            "workflow definitions, or the effective diff"
        ),
        "if any binding changed or is unknown",
        "reacquire only the affected evidence",
    ):
        assert invariant in text



def test_adapter_success_path_is_review_evidence_oriented() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "CI_GREEN -> REVIEW_EVIDENCE_PENDING -> REVIEW_EVIDENCE_ESTABLISHED" in text
    assert "CI_GREEN -> REVIEW_EVIDENCE_PENDING -> REVIEW_REQUESTED" not in text
    assert "REVIEW_REQUESTED -> REVIEW_COMPLETED" not in text
    assert "Issuing a review request is not an acceptance state" in text


def test_adapter_accepts_evidence_independently_of_acquisition_transport() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for phrase in (
        "the gate evaluates evidence, not the transport",
        "completed independent review bound to the exact current pr head",
        "explicit cumulative coverage bound to the ordered stack",
        "review-request transport is not itself acceptance evidence",
    ):
        assert phrase in text


def test_adapter_keeps_missing_evidence_fail_closed_and_handoff_separate() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    assert "review_evidence_pending" in text
    assert "blocked_review_missing" in text
    assert "human handoff does not establish review evidence" in text
    assert "do not transition to merge_allowed" in text


def test_adapter_preserves_serial_acquisition_without_making_it_gate_state() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    assert "when serial-pr acquisition is selected" in text
    assert "may request review for the exact current head" in text
    assert "must name the exact sha" in text
    assert "request_requested" not in text

def test_adapter_requires_exact_head_review_and_guarded_merge() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "request review for the exact current head",
        "the request must name the exact sha",
        (
            "a request, pending review, empty review list, or absence of findings "
            "is not completed review evidence"
        ),
        "current pr head equals the exact accepted head",
        "never omit `expected_head_sha`",
        "do not retry blindly",
    ):
        assert invariant in text


def test_adapter_uses_review_feedback_disposition_procedure() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    reference = FEEDBACK_REFERENCE.read_text(encoding="utf-8")

    assert "references/review-feedback-disposition.md" in skill
    assert "Treat each review item as a hypothesis to verify or falsify" in skill
    assert "Classification explains remediation ownership" in skill
    assert "Keep an item unresolved while its evidence is insufficient" in skill
    assert "evidence-backed no-change reason" in skill

    categories = (
        "actual-defect",
        "invariant-gap",
        "regression-test-gap",
        "documentation-ambiguity",
        "reviewer-misunderstanding",
        "unrelated-suggestion",
    )
    for category in categories:
        assert f"`{category}`" in skill
        assert f"`{category}`" in reference


def test_feedback_disposition_reference_preserves_authority_and_head_binding() -> None:
    text = FEEDBACK_REFERENCE.read_text(encoding="utf-8").lower()
    for invariant in (
        "does not create semantic review policy",
        "reviewer text as a defect hypothesis, not as authority",
        "keep the item unresolved",
        "historical or stale-head review comments may be useful diagnostic inputs",
        "they are not exact-head acceptance evidence",
        "smallest generalized root cause",
        "make no appeasement edit",
        "does not override severity",
        "the exact proposed head against which the claim was verified or falsified",
        "reacquire only the evidence invalidated by that change",
        "thread resolution is bookkeeping evidence of disposition",
    ):
        assert invariant in text


def test_adapter_uses_immutable_head_guard_instead_of_redundant_last_poll() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    assert "use the immutable-head guard to close the proposed-head race" in text
    assert "rather than inserting an extra unrequired head poll" in text


def test_adapter_separates_merge_from_post_merge_readiness() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "confirm the pr is actually merged",
        "record the merge commit sha",
        (
            "treat release, publication, deployment, and other post-merge readiness "
            "as separate boundaries"
        ),
    ):
        assert invariant in text


def test_adapter_supports_strategy_neutral_human_handoff_and_stacked_coverage() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "serial-pr",
        "stacked-pr",
        "agent-review-and-merge",
        "human-handoff",
        "handoff_ready",
        "does not request review",
        "does not authorize or execute a merge",
        "ordered stack",
        "integration base",
        "each member exact head",
        "cumulative scope",
        "review contract",
        "reviewer independence",
        "review completion state",
        "material limitations",
        "tip pr review event",
        "do not mechanically mark every unaffected item stale",
        "applicability is unknown",
    ):
        assert invariant in text

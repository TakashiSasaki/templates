from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_RULE = ROOT / "policy" / "pull-request" / "review-result-discovery.md"
APPLICABILITY_RULE = (
    ROOT / "policy" / "pull-request" / "review-result-applicability.md"
)
EXACT_HEAD_RULE = ROOT / "policy" / "pull-request" / "independent-exact-head-review.md"
CLOSURE_RULE = ROOT / "policy" / "pull-request" / "review-thread-closure.md"
REACQUISITION_RULE = (
    ROOT
    / "policy"
    / "pull-request"
    / "review-reacquisition-after-disposition.md"
)
REFERENCES = ROOT / "skills" / "pr-merge-gate" / "references"
GITHUB_DISCOVERY = REFERENCES / "github-review-result-discovery.md"
SKILL = ROOT / "skills" / "pr-merge-gate" / "SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_clean_submission_cannot_hide_finding_on_another_surface() -> None:
    policy = _text(DISCOVERY_RULE)
    adapter = _text(GITHUB_DISCOVERY)
    skill = _text(SKILL)

    assert "absence of findings on any single provider surface" in policy
    assert (
        "clean review body does not negate an actionable inline thread or ordinary comment"
        in adapter
    )
    assert "a finding remains actionable when another surface is clean" in skill


def test_latest_request_is_purpose_aware_not_timestamp_only() -> None:
    policy = _text(APPLICABILITY_RULE)
    adapter = _text(GITHUB_DISCOVERY)
    skill = _text(SKILL)

    assert "latest applicable review request" in policy
    assert (
        "does not supersede a different purpose merely because its request is newer"
        in policy
    )
    assert "do not select a request solely because it is the newest event" in adapter
    assert "applicable review purpose and latest applicable review request/cycle" in skill


def test_exact_head_completion_and_historical_finding_applicability_are_separate() -> None:
    applicability = _text(APPLICABILITY_RULE)
    exact_head = _text(EXACT_HEAD_RULE)
    reacquisition = _text(REACQUISITION_RULE)
    skill = _text(SKILL)

    assert "completed review is stale for merge acceptance" in applicability
    assert "exact proposed head" in exact_head
    assert "do not discard a finding solely because the head changed" in applicability
    assert (
        "it does not erase an earlier finding whose causal condition remains applicable"
        in reacquisition
    )
    assert (
        "do not discard an older finding solely because completion evidence for its "
        "source review became stale"
    ) in skill


def test_reaction_only_cannot_establish_completed_problem_free_review() -> None:
    policy = _text(DISCOVERY_RULE)
    adapter = _text(GITHUB_DISCOVERY)

    assert "uninterpreted provider state" in policy
    assert (
        "do not interpret an acknowledgement or attention signal as review completion"
        in policy
    )
    assert "must not be promoted to completed review, approval, or `no findings`" in adapter


def test_body_only_and_comment_only_findings_require_closure() -> None:
    closure = _text(CLOSURE_RULE)
    reacquisition = _text(REACQUISITION_RULE)
    skill = _text(SKILL)

    assert "ordinary comments" in closure
    assert "top-level review body" in closure
    assert "ordinary pull-request comment" in reacquisition
    assert "non-thread finding dispositions" in skill
    assert "finding-level closure evidence" in skill


def test_merge_gate_directly_lists_new_canonical_rules_and_unknown_applicability_block() -> None:
    skill = _text(SKILL)

    assert "`pull-request.discover-review-results-across-applicable-surfaces`" in skill
    assert (
        "`pull-request.bind-review-result-classification-to-applicable-cycle-and-revision`"
        in skill
    )
    assert "`blocked_review_applicability_unknown`" in skill
    assert "do not infer completion or `no findings` from a clean or empty surface" in skill

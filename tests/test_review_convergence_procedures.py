from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MERGE_GATE = ROOT / "skills" / "pr-merge-gate" / "SKILL.md"
PREFLIGHT = (
    ROOT
    / "skills"
    / "pr-merge-gate"
    / "references"
    / "review-acquisition-preflight.md"
)
FEEDBACK = (
    ROOT
    / "skills"
    / "pr-merge-gate"
    / "references"
    / "review-feedback-disposition.md"
)
BATCHING = (
    ROOT
    / "skills"
    / "pr-merge-gate"
    / "references"
    / "head-mutation-batching.md"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_merge_gate_wires_revision_bound_review_preflight() -> None:
    skill = _text(MERGE_GATE)
    reference = _text(PREFLIGHT)

    assert "references/review-acquisition-preflight.md" in skill
    assert "pull-request.preflight-review-acquisition" in skill
    assert "before invoking the reviewer" in skill
    assert "do not invoke the reviewer with that binding" in skill

    for phrase in (
        "current pull request head sha",
        "ref currently resolves to the same sha",
        "ordered member list",
        "stack tip exact sha",
        "acquisition failure",
        "not establish that the provider accepted the request",
        "fixed waiting period",
    ):
        assert phrase in reference


def test_review_feedback_performs_bounded_sibling_root_cause_audit() -> None:
    skill = _text(MERGE_GATE)
    feedback = _text(FEEDBACK)

    assert "bounded sibling-dimension audit" in skill
    for phrase in (
        "bounded sibling dimensions",
        "success versus failure completion",
        "current versus stale generation",
        "required converse or completeness condition",
        "missing, malformed, extra, duplicate",
        "actual containing layout",
        "not permission for open-ended neighboring cleanup",
    ):
        assert phrase in feedback


def test_diagnostic_validation_and_qualification_remain_distinct() -> None:
    text = _text(BATCHING)
    for phrase in (
        "diagnostic validation",
        "qualification validation",
        "purpose is feedback",
        "exact candidate revision or artifact",
        "do not deliberately spend an expensive full qualification cycle",
        "never substitute a diagnostic pass for required qualification",
        "naturally triggered repository ci",
    ):
        assert phrase in text

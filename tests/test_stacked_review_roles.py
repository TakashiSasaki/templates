from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "policy" / "pull-request" / "stacked-review-coverage.md"
GATE = ROOT / "skills" / "pr-merge-gate" / "references" / "stacked-review-coverage.md"
STACKED = ROOT / "skills" / "orchestrate-repository-change" / "references" / "stacked-pr-workflow.md"
HANDOFF = ROOT / "skills" / "orchestrate-repository-change" / "references" / "human-handoff.md"
ORCHESTRATOR = ROOT / "skills" / "orchestrate-repository-change" / "SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_individual_exact_head_review_is_ordinary_member_acceptance_path() -> None:
    policy = _text(POLICY)
    gate = _text(GATE)
    stacked = _text(STACKED)
    assert "ordinary merge-acceptance path" in policy
    assert "individual independent exact-head review" in gate
    assert "ordinary merge-acceptance path" in stacked


def test_whole_stack_audit_is_not_inferred_as_lower_member_merge_evidence() -> None:
    for text in (_text(POLICY), _text(GATE), _text(STACKED)):
        assert "tip-only" in text or "stack tip" in text
        assert "cumulative" in text
    assert "architecture/dependency/completeness audit" in _text(STACKED)
    assert "not per-member merge evidence" in _text(ORCHESTRATOR)


def test_incomplete_cumulative_binding_falls_back_without_review_loop() -> None:
    policy = _text(POLICY)
    gate = _text(GATE)
    assert "use the ordinary individual exact-head review path" in policy
    assert "do not repeatedly request cumulative clarification" in policy
    assert "fall back to individual exact-head review" in gate
    assert "do not create a repeated cumulative-review or clarification loop" in gate


def test_human_handoff_keeps_final_audit_separate_from_acceptance_review() -> None:
    handoff = _text(HANDOFF)
    orchestrator = _text(ORCHESTRATOR)
    for text in (handoff, orchestrator):
        assert "explicit task instruction" in text
        assert "whole-stack" in text
        assert "merge evidence" in text
        assert "merge authorization" in text
    assert "review-retry loop" in handoff
    assert "do not turn it into a retry loop" in orchestrator

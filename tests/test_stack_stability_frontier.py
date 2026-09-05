from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACKED = (
    ROOT
    / "skills"
    / "orchestrate-repository-change"
    / "references"
    / "stacked-pr-workflow.md"
)
SELECTION = (
    ROOT
    / "skills"
    / "orchestrate-repository-change"
    / "references"
    / "pr-workflow-selection.md"
)
HUMAN_HANDOFF = (
    ROOT
    / "skills"
    / "orchestrate-repository-change"
    / "references"
    / "human-handoff.md"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_stability_frontier_is_planning_state_not_merge_or_review_state() -> None:
    text = _text(STACKED)
    for phrase in (
        "stability frontier",
        "no further head change is planned",
        "new material defect",
        "authority decision",
        "scope correction",
        "does not mean the member is merged",
        "reviewed",
        "immutable forever",
    ):
        assert phrase in text


def test_review_latency_does_not_block_dependency_safe_stack_construction() -> None:
    text = _text(STACKED)
    for phrase in (
        "review latency alone does not move the frontier backward",
        "does not block dependency-safe implementation",
        "construct later members on the current exact parent head",
        "do not create a cosmetic or mechanical lower-head rewrite",
    ):
        assert phrase in text


def test_known_upstream_repair_defers_only_downstream_final_identity_materialization() -> None:
    text = _text(STACKED)
    for phrase in (
        "known upstream semantic repair",
        "necessarily stale a downstream immutable identity",
        "defer that downstream **final materialization**",
        "does not prohibit implementation of the downstream logic",
        "knowingly manufacturing final immutable evidence",
    ):
        assert phrase in text


def test_lower_merge_does_not_force_mechanical_upper_rewrite() -> None:
    text = _text(STACKED)
    for phrase in (
        "according to actual bindings",
        "do not mechanically rewrite the upper head solely to record the lower merge",
        "invalidate only the evidence whose binding changed",
    ):
        assert phrase in text


def test_final_whole_stack_review_freezes_intended_heads_without_becoming_merge_evidence() -> None:
    text = _text(STACKED)
    for phrase in (
        "final revision-bound whole-stack review",
        "freeze the exact candidate heads",
        "architecture/dependency/completeness audit",
        "not lower-member merge evidence",
        "pending required ci blocks the final review request",
    ):
        assert phrase in text


def test_final_whole_stack_review_requires_complete_ledger_before_invocation() -> None:
    stacked = _text(STACKED)
    handoff = _text(HUMAN_HANDOFF)

    stacked_gate = stacked.index(
        "pull-request.disposition-known-findings-before-review-reacquisition"
    )
    stacked_invoke = stacked.index("do not invoke the whole-stack reviewer")
    assert stacked_gate < stacked_invoke
    assert "complete logical finding backlog" in stacked
    assert "required finding-level closure evidence" in stacked
    assert "re-evaluate the complete known-finding gate immediately before reviewer invocation" in stacked

    handoff_gate = handoff.index(
        "pull-request.disposition-known-findings-before-review-reacquisition"
    )
    handoff_invoke = handoff.index("immediately before reviewer invocation")
    assert handoff_gate < handoff_invoke
    assert "complete logical finding backlog" in handoff
    assert "required finding-level closure evidence" in handoff
    assert "do not request the audit while any known material finding lacks" in handoff


def test_pr_boundary_selection_accounts_for_propagation_and_invalidation_costs() -> None:
    text = _text(SELECTION)
    for phrase in (
        "authority boundary",
        "semantic purpose",
        "independent merge value",
        "rollback unit",
        "validation boundary",
        "review comprehensibility",
        "expected head stability",
        "cross-member coupling",
        "descendant propagation cost",
        "evidence invalidation cost",
        "split benefit > restack / invalidation / coordination cost",
        "heuristic, not a mandatory acceptance gate",
        "do not optimize for a fixed pr count",
    ):
        assert phrase in text

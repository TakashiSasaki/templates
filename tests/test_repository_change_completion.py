from __future__ import annotations

from pathlib import Path

import yaml

from agent_policy.policy_loader import parse_policy

ROOT = Path(__file__).resolve().parents[1]
CORE_PROFILE = ROOT / "profiles" / "core.yml"
COMPLETION = ROOT / "policy" / "core" / "repository-change-completion.md"
HUMAN_HANDOFF = (
    ROOT
    / "skills"
    / "orchestrate-repository-change"
    / "references"
    / "human-handoff.md"
)


def test_completion_semantics_are_selected_by_core_profile() -> None:
    profile = yaml.safe_load(CORE_PROFILE.read_text(encoding="utf-8"))
    assert "policy/core/repository-change-completion.md" in profile["policy_files"]

    text = COMPLETION.read_text(encoding="utf-8")
    assert parse_policy(
        COMPLETION,
        "policy/core/repository-change-completion.md",
        "toolchain",
    ).id == "changes.separate-task-review-merge-state"
    for semantic in (
        "human-handoff",
        "not a review waiver",
        "merge authorization as not established",
        "open and unmerged",
        "handoff_ready",
        "merge_ready",
        "merged",
    ):
        assert semantic in text.lower()


def test_completion_semantics_do_not_turn_handoff_into_merge_acceptance() -> None:
    text = COMPLETION.read_text(encoding="utf-8").lower()
    assert "does not authorize a merge" in text
    assert "does not remove acceptance requirements" in text


def test_handoff_forbids_new_review_acquisition_without_erasing_existing_evidence() -> None:
    text = COMPLETION.read_text(encoding="utf-8").lower()
    assert "must not initiate a new review request" in text
    assert "reviewer assignment" in text
    assert "provider invocation" in text
    assert "any other review-request mechanism" in text
    assert "existing review evidence may be observed, inspected, and reported" in text


def test_handoff_reports_preexisting_completed_review_truthfully() -> None:
    text = COMPLETION.read_text(encoding="utf-8").lower()
    assert "when no applicable pre-existing review evidence" in text
    assert "report independent review as not requested or outstanding" in text
    assert "applicable pre-existing review evidence already establishes completed review" in text
    assert "preserve and report that review_complete state" in text
    assert "must not label a handoff review complete unless applicable pre-existing" in text


def test_handoff_ready_does_not_erase_preexisting_completed_review_state() -> None:
    text = HUMAN_HANDOFF.read_text(encoding="utf-8").lower()
    assert "handoff_ready does not by itself imply review_complete" in text
    assert "handoff_ready is not review_complete" not in text


def test_progression_does_not_force_completion_boundary() -> None:
    text = COMPLETION.read_text(encoding="utf-8").lower()
    assert "progression controls construction ordering" in text
    assert "completion controls the agent's stopping boundary" in text
    assert "must not by itself force review acquisition or merge completion" in text

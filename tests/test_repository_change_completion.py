from __future__ import annotations

from pathlib import Path

import yaml

from agent_policy.policy_loader import parse_policy

ROOT = Path(__file__).resolve().parents[1]
CORE_PROFILE = ROOT / "profiles" / "core.yml"
COMPLETION = ROOT / "policy" / "core" / "repository-change-completion.md"


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

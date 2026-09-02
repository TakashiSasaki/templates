from __future__ import annotations

from pathlib import Path

from agent_policy.config import package_root
from agent_policy.renderer import GENERATED_MARKER, NON_GENERATED_SKILLS, render_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "orchestrate-repository-change"
SKILL = ROOT / "skills" / SKILL_NAME / "SKILL.md"
RATIONALE = ROOT / "docs" / "agent-work-orchestration.md"


def test_orchestration_skill_is_generated_and_renderable() -> None:
    assert (package_root() / "skills" / SKILL_NAME).is_dir()
    assert SKILL_NAME not in NON_GENERATED_SKILLS

    rendered = render_skill(SKILL_NAME)
    assert set(rendered) == {"SKILL.md"}
    assert GENERATED_MARKER in rendered["SKILL.md"]
    assert "name: orchestrate-repository-change" in rendered["SKILL.md"]


def test_orchestration_skill_preserves_acceptance_authority() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "execution-efficiency procedure, not a new source of semantic acceptance policy",
        "repository code, schemas, validators, tests, workflows, release rules",
        "do not impose a fixed numeric limit on tool calls",
        "do not combine unrelated work merely to reduce commit, pull-request, or tool-call counts",
        "never skip a required expensive check merely because a cheaper check passed",
        "candidate stability is an efficiency mechanism, not evidence",
        "do not expand completion criteria because additional checks feel safer",
        "do not omit explicitly required completion criteria because they are expensive",
    ):
        assert invariant in text


def test_orchestration_skill_covers_round_trip_and_evidence_churn_controls() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "batch or parallelize them",
        "one coherent mutation over avoidable one-finding-at-a-time churn",
        "use asynchronous wait time for bounded read-only work",
        "do not turn wait time into an unbounded search for hypothetical defects",
        "aggregate known actionable findings before mutating",
        "do not wait an arbitrary interval for hypothetical future findings",
        "invalidate only evidence whose binding changed or became unknown",
        "selective invalidation must never become an excuse to reuse stale evidence",
        "prefer guarded writes over redundant pre-write polling",
        "do not retry blindly",
    ):
        assert invariant in text


def test_orchestration_skill_keeps_provider_and_reviewer_triggers_out_of_shared_procedure() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for provider_specific in (
        "@hermes review",
        "hermes agent",
        "copilot-pull-request-reviewer",
        "openai codex",
    ):
        assert provider_specific not in text


def test_orchestration_rationale_keeps_metrics_diagnostic_only() -> None:
    text = RATIONALE.read_text(encoding="utf-8").lower()
    for metric in (
        "state_read_amplification",
        "review_amplification",
        "ci_amplification",
        "post_review_head_churn",
        "evidence_reuse_ratio",
    ):
        assert metric in text

    assert "diagnostic observations rather than merge gates" in text
    assert "procedure guidance should not be promoted merely because it usually saves time" in text
    assert "`audit-frozen-change` remains" in text
    assert "`pr-merge-gate` remains" in text

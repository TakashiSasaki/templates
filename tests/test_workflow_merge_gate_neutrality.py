from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".agent-policy.yml"
GATE = ROOT / "skills/pr-merge-gate/SKILL.md"


def test_workflow_selection_is_not_persisted_as_profiles_or_schema_fields() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert "workflow" not in config
    profile_names = {
        path.stem for path in (ROOT / "profiles").glob("*.yml")
    }
    assert not {"serial-pr", "stacked-pr", "human-handoff"} & profile_names


def test_merge_gate_reports_handoff_without_claiming_merge_readiness() -> None:
    text = GATE.read_text(encoding="utf-8").lower()
    for phrase in (
        "human-handoff",
        "handoff_ready",
        "does not initiate a new review request",
        "does not authorize or execute a merge",
        "not a waiver",
        "not merge-ready",
        "review-acquisition method",
        "cumulative coverage",
        "tip-only review",
        "fail-closed",
    ):
        assert phrase in text


def test_merge_gate_does_not_require_review_request_transport() -> None:
    text = GATE.read_text(encoding="utf-8")
    assert "CI_GREEN -> REVIEW_EVIDENCE_PENDING -> REVIEW_EVIDENCE_ESTABLISHED" in text
    assert "CI_GREEN -> REVIEW_EVIDENCE_PENDING -> REVIEW_REQUESTED" not in text
    assert "Issuing a review request is not an acceptance state" in text
    assert "The gate evaluates evidence, not the transport" in text


def test_stacked_progression_accepts_individual_or_cumulative_review_evidence() -> None:
    text = GATE.read_text(encoding="utf-8").lower()
    assert "including a member constructed under stacked-pr progression" in text
    assert "completed independent review bound to that member's exact current head" in text
    assert "when one completed review is claimed to cover multiple stacked members" in text
    assert "valid cumulative evidence must additionally bind" in text
    assert "stacked progression does not require cumulative review" in text
    assert (
        "a tip-only review or approval event does not establish lower-member "
        "cumulative coverage"
    ) in text


def test_review_acquisition_depends_on_completion_not_progression() -> None:
    text = GATE.read_text(encoding="utf-8").lower()
    assert (
        "review acquisition belongs to the selected completion procedure, not to "
        "serial or stacked progression"
    ) in text
    assert "under agent-review-and-merge" in text
    assert "under human-handoff, do not initiate a new review request" in text


def test_generated_orchestration_projection_contains_all_procedures() -> None:
    skill = (
        ROOT / ".agents/skills/orchestrate-repository-change/SKILL.md"
    ).read_text(encoding="utf-8")
    for reference in (
        "references/pr-workflow-selection.md",
        "references/serial-pr-workflow.md",
        "references/stacked-pr-workflow.md",
        "references/human-handoff.md",
    ):
        assert reference in skill

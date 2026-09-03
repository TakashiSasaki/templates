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
        "does not request review",
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


def test_stacked_and_serial_evidence_sources_are_distinct() -> None:
    text = GATE.read_text(encoding="utf-8").lower()
    assert "for a serial candidate, valid evidence is a completed independent review" in text
    assert "for a stacked candidate, valid evidence is explicit cumulative coverage" in text
    assert "a tip-only review or approval event does not establish lower-member coverage" in text
    assert "human handoff does not establish review evidence" in text

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

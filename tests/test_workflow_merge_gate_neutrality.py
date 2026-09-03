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

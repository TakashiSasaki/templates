from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "orchestrate-repository-change" / "SKILL.md"
REFERENCES = ROOT / "skills" / "orchestrate-repository-change" / "references"
SELECTION = REFERENCES / "pr-workflow-selection.md"
STAGED = REFERENCES / "staged-ci-execution.md"
WORK_LEDGER = REFERENCES / "work-ledger.md"


def test_workflow_selection_makes_ci_staging_strategy_neutral() -> None:
    text = SELECTION.read_text(encoding="utf-8").lower()
    assert "validation staging is orthogonal to pr strategy" in text
    assert "staged ci execution" in text
    assert "ci preflight, core validation, conditional integration" in text
    assert "full qualification" in text


def test_staged_execution_orders_cheap_falsification_without_serializing_everything() -> None:
    text = STAGED.read_text(encoding="utf-8").lower()
    for fragment in (
        "use ci preflight for early falsification",
        "complete core validation",
        "classify conditional applicability",
        "run applicable conditional integration",
        "freeze at the authority boundary",
        "complete exact-head qualification",
        "supersede stale expensive work",
    ):
        assert fragment in text
    assert "not a requirement for a purely serial workflow" in text
    assert "repository-required automatic checks must not be suppressed" in text


def test_staged_execution_keeps_applicability_and_work_ledger_non_authoritative() -> None:
    staged = STAGED.read_text(encoding="utf-8").lower()
    ledger = WORK_LEDGER.read_text(encoding="utf-8").lower()
    assert "unknown or unsafe classification fails closed" in staged
    assert "`not-applicable` is not pass evidence" in staged
    assert "stage label is operational metadata" in staged
    assert "applicability conditions" in ledger
    assert "a ledger label such as `success`, `qualified`" in ledger


def test_main_orchestrator_reaches_strategy_selection_and_preserves_focused_to_broad_rule() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    assert "references/pr-workflow-selection.md" in text
    assert "validate from focused to broad unless parallelism is cheaper" in text
    assert "never skip a required expensive check merely because a cheaper check passed" in text

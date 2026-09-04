from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = ROOT / "skills" / "orchestrate-repository-change" / "SKILL.md"
STACKED = (
    ROOT
    / "skills"
    / "orchestrate-repository-change"
    / "references"
    / "stacked-pr-workflow.md"
)
BATCHING = ROOT / "skills" / "pr-merge-gate" / "references" / "head-mutation-batching.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_stabilization_precedes_intentional_expensive_review_acquisition() -> None:
    orchestrator = _text(ORCHESTRATOR)
    stacked = _text(STACKED)
    batching = _text(BATCHING)
    for text in (orchestrator, stacked, batching):
        assert "stabiliz" in text
        assert "known" in text
        assert "focused validation" in text
        assert "generated" in text
        assert "material defect" in text
        assert "immutable" in text
    assert "do not deliberately acquire independent review" in orchestrator
    assert "do not deliberately review a knowingly intermediate downstream head" in stacked
    assert "do not deliberately request independent review" in batching


def test_stabilization_is_not_a_hidden_waiting_gate() -> None:
    orchestrator = _text(ORCHESTRATOR)
    stacked = _text(STACKED)
    batching = _text(BATCHING)
    for text in (orchestrator, stacked, batching):
        assert "not" in text
        assert "wait" in text
        assert "pr-creation gate" in text or "pr creation" in text
    assert "continue useful downstream implementation" in orchestrator
    assert "continue useful dependent implementation" in stacked
    assert "naturally triggered ci may run before stabilization" in batching


def test_stabilization_does_not_weaken_post_mutation_exact_head_evidence() -> None:
    batching = _text(BATCHING)
    assert "exact-head ci" in batching
    assert "exact-head review" in batching
    assert "reacquire every exact-head gate invalidated by the mutation" in batching
    assert "not acceptance evidence" in batching
